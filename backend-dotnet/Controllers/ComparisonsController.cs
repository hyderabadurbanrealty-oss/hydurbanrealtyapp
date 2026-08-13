using HyderabadUrbanReality.Core.DTOs;
using HyderabadUrbanReality.Core.Entities;
using HyderabadUrbanReality.Core.Filters;
using HyderabadUrbanReality.Core.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using System.Security.Claims;

namespace HyderabadUrbanReality.Controllers
{
    /// <summary>
    /// Comparison Results endpoints.
    /// Requires JWT + verified email (Req 17.4).
    /// </summary>
    [ApiController]
    [Route("api/user/comparisons")]
    [Authorize]
    [RequireVerifiedEmail]
    public class ComparisonsController : ControllerBase
    {
        private readonly IUserDataRepository _dataRepo;
        private readonly IProjectRepository  _projectRepo;

        public ComparisonsController(IUserDataRepository dataRepo, IProjectRepository projectRepo)
        {
            _dataRepo    = dataRepo;
            _projectRepo = projectRepo;
        }

        // GET /api/user/comparisons
        [HttpGet]
        public async Task<IActionResult> GetAll()
        {
            var userId      = GetUserId();
            var comparisons = await _dataRepo.GetComparisonsAsync(userId);
            var dtos = comparisons.Select(c =>
                new ComparisonResultDto(c.Id, c.Name, c.ProjectIds, c.CreatedAt));
            return Ok(dtos);
        }

        // POST /api/user/comparisons
        [HttpPost]
        public async Task<IActionResult> Add([FromBody] AddComparisonRequestDto dto)
        {
            if (dto.ProjectIds is null || dto.ProjectIds.Length < 2)
                return BadRequest(new { error = "at_least_two_projects_required" });

            var userId = GetUserId();

            // Validate all project IDs exist (Req 16.7)
            var invalid = new List<string>();
            foreach (var pid in dto.ProjectIds)
                if (!await _projectRepo.ProjectExistsAsync(pid))
                    invalid.Add(pid);

            if (invalid.Count > 0)
                return UnprocessableEntity(new { error = "invalid_project_ids", invalidIds = invalid });

            var comparison = new ComparisonResult
            {
                Id         = Guid.NewGuid(),
                UserId     = userId,
                Name       = dto.Name,
                ProjectIds = dto.ProjectIds,
            };
            var created = await _dataRepo.AddComparisonAsync(comparison);
            return StatusCode(201, new ComparisonResultDto(
                created.Id, created.Name, created.ProjectIds, created.CreatedAt));
        }

        // GET /api/user/comparisons/{id}
        [HttpGet("{id:guid}")]
        public async Task<IActionResult> GetById(Guid id)
        {
            var userId = GetUserId();
            var comp   = await _dataRepo.GetComparisonAsync(userId, id);

            if (comp is null)
            {
                // Determine 403 vs 404: check if it exists for any user
                // For simplicity return 404 (ownership detail hidden)
                return NotFound(new { error = "not_found" });
            }

            return Ok(new
            {
                comp.Id,
                comp.Name,
                comp.ProjectIds,
                comp.Snapshot,
                comp.CreatedAt,
            });
        }

        // DELETE /api/user/comparisons/{id}
        [HttpDelete("{id:guid}")]
        public async Task<IActionResult> Delete(Guid id)
        {
            var userId = GetUserId();
            var comp   = await _dataRepo.GetComparisonAsync(userId, id);
            if (comp is null) return NotFound(new { error = "not_found" });

            await _dataRepo.DeleteComparisonAsync(userId, id);
            return NoContent();
        }

        private Guid GetUserId() =>
            Guid.Parse(User.FindFirstValue(ClaimTypes.NameIdentifier)
                ?? User.FindFirstValue("sub")!);
    }
}
