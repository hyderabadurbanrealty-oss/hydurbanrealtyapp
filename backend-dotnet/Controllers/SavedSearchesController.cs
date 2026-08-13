using HyderabadUrbanReality.Core.DTOs;
using HyderabadUrbanReality.Core.Entities;
using HyderabadUrbanReality.Core.Filters;
using HyderabadUrbanReality.Core.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using System.Security.Claims;
using System.Text.Json;

namespace HyderabadUrbanReality.Controllers
{
    /// <summary>
    /// Saved Searches endpoints.
    /// Requires JWT + verified email (Req 17.4).
    /// </summary>
    [ApiController]
    [Route("api/user/saved-searches")]
    [Authorize]
    [RequireVerifiedEmail]
    public class SavedSearchesController : ControllerBase
    {
        private readonly IUserDataRepository _dataRepo;
        private readonly IProjectRepository  _projectRepo;

        public SavedSearchesController(IUserDataRepository dataRepo, IProjectRepository projectRepo)
        {
            _dataRepo    = dataRepo;
            _projectRepo = projectRepo;
        }

        // GET /api/user/saved-searches
        [HttpGet]
        public async Task<IActionResult> GetAll()
        {
            var userId  = GetUserId();
            var searches = await _dataRepo.GetSavedSearchesAsync(userId);
            var dtos = searches.Select(s =>
            {
                JsonElement filters;
                try { filters = JsonDocument.Parse(s.Filters).RootElement; }
                catch { filters = JsonDocument.Parse("{}").RootElement; }
                return new SavedSearchDto(s.Id, s.Name, filters, s.ResultCount, s.LastRunAt, s.CreatedAt);
            });
            return Ok(dtos);
        }

        // POST /api/user/saved-searches
        [HttpPost]
        public async Task<IActionResult> Add([FromBody] AddSavedSearchRequestDto dto)
        {
            var userId = GetUserId();
            var search = new SavedSearch
            {
                Id      = Guid.NewGuid(),
                UserId  = userId,
                Name    = dto.Name,
                Filters = dto.Filters.GetRawText(),
            };
            var created = await _dataRepo.AddSavedSearchAsync(search);
            var filtersElem = JsonDocument.Parse(created.Filters).RootElement;
            return StatusCode(201, new SavedSearchDto(
                created.Id, created.Name, filtersElem,
                created.ResultCount, created.LastRunAt, created.CreatedAt));
        }

        // PUT /api/user/saved-searches/{id}
        [HttpPut("{id:guid}")]
        public async Task<IActionResult> Update(Guid id, [FromBody] UpdateSavedSearchRequestDto dto)
        {
            var userId = GetUserId();
            JsonDocument? filtersDoc = dto.Filters.HasValue
                ? JsonDocument.Parse(dto.Filters.Value.GetRawText())
                : null;

            var updated = await _dataRepo.UpdateSavedSearchAsync(userId, id, dto.Name, filtersDoc);
            if (updated is null)
            {
                var existing = await _dataRepo.GetSavedSearchAsync(userId, id);
                return existing is null
                    ? NotFound(new { error = "not_found" })
                    : StatusCode(403, new { error = "forbidden" });
            }
            var filtersElem = JsonDocument.Parse(updated.Filters).RootElement;
            return Ok(new SavedSearchDto(
                updated.Id, updated.Name, filtersElem,
                updated.ResultCount, updated.LastRunAt, updated.CreatedAt));
        }

        // DELETE /api/user/saved-searches/{id}
        [HttpDelete("{id:guid}")]
        public async Task<IActionResult> Delete(Guid id)
        {
            var userId   = GetUserId();
            var existing = await _dataRepo.GetSavedSearchAsync(userId, id);
            if (existing is null) return NotFound(new { error = "not_found" });

            await _dataRepo.DeleteSavedSearchAsync(userId, id);
            return NoContent();
        }

        // POST /api/user/saved-searches/{id}/run
        [HttpPost("{id:guid}/run")]
        public async Task<IActionResult> Run(Guid id)
        {
            var userId   = GetUserId();
            var search   = await _dataRepo.GetSavedSearchAsync(userId, id);
            if (search is null) return NotFound(new { error = "not_found" });

            // Parse filters
            JsonElement filtersElem;
            try { filtersElem = JsonDocument.Parse(search.Filters).RootElement; }
            catch { return BadRequest(new { error = "invalid_filters" }); }

            // Apply filters against projects (Req 15.5, 15.8)
            var allProjects = await _projectRepo.GetAllProjectsAsync();
            var results     = ApplyFilters(allProjects, filtersElem);

            // Update run stats
            await _dataRepo.UpdateSavedSearchRunStatsAsync(id, results.Count);

            return Ok(new { searchId = id, resultCount = results.Count, projects = results });
        }

        // ── Private ───────────────────────────────────────────────────────────

        private static List<Dictionary<string, object>> ApplyFilters(
            IEnumerable<Dictionary<string, object>> projects,
            JsonElement filters)
        {
            var list = projects.ToList();

            if (filters.TryGetProperty("pinCodes", out var pinCodesEl))
            {
                var pins = pinCodesEl.EnumerateArray()
                    .Select(p => p.GetString() ?? "").Where(p => p.Length > 0).ToHashSet();
                if (pins.Count > 0)
                    list = list.Where(p => pins.Contains(GetStr(p, "pin_code") ?? GetStr(p, "pinCode") ?? "")).ToList();
            }

            if (filters.TryGetProperty("district", out var distEl) && distEl.GetString() is string dist && dist.Length > 0)
                list = list.Where(p => string.Equals(GetStr(p, "district"), dist, StringComparison.OrdinalIgnoreCase)).ToList();

            if (filters.TryGetProperty("projectStatus", out var statusEl) && statusEl.GetString() is string status && status.Length > 0)
                list = list.Where(p => string.Equals(GetStr(p, "project_status") ?? GetStr(p, "projectStatus"), status, StringComparison.OrdinalIgnoreCase)).ToList();

            if (filters.TryGetProperty("minFlats", out var minEl) && minEl.TryGetInt32(out int minFlats))
                list = list.Where(p => GetInt(p, "total_flats") >= minFlats).ToList();

            if (filters.TryGetProperty("maxFlats", out var maxEl) && maxEl.TryGetInt32(out int maxFlats))
                list = list.Where(p => GetInt(p, "total_flats") <= maxFlats).ToList();

            if (filters.TryGetProperty("sortBy", out var sortEl) && sortEl.GetString() is string sortBy)
            {
                list = sortBy switch
                {
                    "bookingPercent" => list.OrderByDescending(p => GetInt(p, "total_booked")).ToList(),
                    "projectName"    => list.OrderBy(p => GetStr(p, "project_name")).ToList(),
                    _                => list,
                };
            }

            return list;
        }

        private static string? GetStr(Dictionary<string, object> d, string key) =>
            d.TryGetValue(key, out var v) ? v?.ToString() : null;

        private static int GetInt(Dictionary<string, object> d, string key)
        {
            if (d.TryGetValue(key, out var v) && v is not null)
                return int.TryParse(v.ToString(), out int i) ? i : 0;
            return 0;
        }

        private Guid GetUserId() =>
            Guid.Parse(User.FindFirstValue(ClaimTypes.NameIdentifier)
                ?? User.FindFirstValue("sub")!);
    }
}
