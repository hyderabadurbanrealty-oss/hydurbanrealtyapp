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
    /// Saved Properties endpoints — deliberate project bookmarks.
    /// Requires JWT + verified email (Req 17.4).
    /// </summary>
    [ApiController]
    [Route("api/user/saved-properties")]
    [Authorize]
    [RequireVerifiedEmail]
    public class SavedPropertiesController : ControllerBase
    {
        private readonly IUserDataRepository _dataRepo;
        private readonly IProjectRepository  _projectRepo;
        private readonly IInputSanitizer     _sanitizer;

        public SavedPropertiesController(
            IUserDataRepository dataRepo,
            IProjectRepository projectRepo,
            IInputSanitizer sanitizer)
        {
            _dataRepo    = dataRepo;
            _projectRepo = projectRepo;
            _sanitizer   = sanitizer;
        }

        // GET /api/user/saved-properties
        [HttpGet]
        public async Task<IActionResult> GetAll()
        {
            var userId = GetUserId();
            var items  = await _dataRepo.GetSavedPropertiesAsync(userId);
            var dtos   = items.Select(sp => new SavedPropertyDto(
                sp.Id, sp.ProjectId,
                string.Empty, null, null, null,   // project fields populated by JOIN in repo
                sp.Notes, sp.CreatedAt));
            return Ok(dtos);
        }

        // POST /api/user/saved-properties
        [HttpPost]
        public async Task<IActionResult> Add([FromBody] AddSavedPropertyRequestDto dto)
        {
            var userId = GetUserId();

            // Validate project exists (Req 13.6)
            if (!await _projectRepo.ProjectExistsAsync(dto.ProjectId))
                return NotFound(new { error = "project_not_found" });

            // Check for duplicate (Req 13.2)
            var existing = await _dataRepo.GetSavedPropertyAsync(userId, dto.ProjectId);
            if (existing is not null)
                return Conflict(new { error = "already_saved" });

            var item = new SavedProperty
            {
                Id        = Guid.NewGuid(),
                UserId    = userId,
                ProjectId = dto.ProjectId,
                Notes     = dto.Notes is not null ? _sanitizer.Sanitize(dto.Notes) : null,
            };
            var created = await _dataRepo.AddSavedPropertyAsync(item);

            return StatusCode(201, new SavedPropertyDto(
                created.Id, created.ProjectId,
                string.Empty, null, null, null,
                created.Notes, created.CreatedAt));
        }

        // DELETE /api/user/saved-properties/{projectId}
        [HttpDelete("{projectId}")]
        public async Task<IActionResult> Remove(string projectId)
        {
            var userId = GetUserId();
            await _dataRepo.RemoveSavedPropertyAsync(userId, projectId);
            return NoContent();
        }

        // GET /api/user/saved-properties/{projectId}/exists
        [HttpGet("{projectId}/exists")]
        public async Task<IActionResult> Exists(string projectId)
        {
            var userId  = GetUserId();
            var existing = await _dataRepo.GetSavedPropertyAsync(userId, projectId);
            return Ok(new { exists = existing is not null });
        }

        private Guid GetUserId() =>
            Guid.Parse(User.FindFirstValue(ClaimTypes.NameIdentifier)
                ?? User.FindFirstValue("sub")!);
    }
}
