using HyderabadUrbanReality.Core.Filters;
using HyderabadUrbanReality.Core.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using System.Security.Claims;

namespace HyderabadUrbanReality.Controllers
{
    /// <summary>
    /// Favorites endpoints — quick heart-button favorites.
    /// Requires JWT + verified email (Req 17.4).
    /// </summary>
    [ApiController]
    [Route("api/user/favorites")]
    [Authorize]
    [RequireVerifiedEmail]
    public class FavoritesController : ControllerBase
    {
        private readonly IUserDataRepository _dataRepo;
        private readonly IProjectRepository  _projectRepo;

        public FavoritesController(IUserDataRepository dataRepo, IProjectRepository projectRepo)
        {
            _dataRepo    = dataRepo;
            _projectRepo = projectRepo;
        }

        // GET /api/user/favorites
        [HttpGet]
        public async Task<IActionResult> GetAll()
        {
            var userId    = GetUserId();
            var favorites = await _dataRepo.GetFavoritesAsync(userId);
            return Ok(favorites);
        }

        // POST /api/user/favorites
        [HttpPost]
        public async Task<IActionResult> Add([FromBody] AddFavoriteRequest dto)
        {
            var userId = GetUserId();

            if (!await _projectRepo.ProjectExistsAsync(dto.ProjectId))
                return NotFound(new { error = "project_not_found" });

            if (await _dataRepo.IsFavoritedAsync(userId, dto.ProjectId))
                return Conflict(new { error = "already_favorited" });

            await _dataRepo.AddFavoriteAsync(userId, dto.ProjectId);
            return StatusCode(201, new { message = "Added to favorites." });
        }

        // DELETE /api/user/favorites/{projectId}
        [HttpDelete("{projectId}")]
        public async Task<IActionResult> Remove(string projectId)
        {
            var userId = GetUserId();
            await _dataRepo.RemoveFavoriteAsync(userId, projectId);
            return NoContent();
        }

        // GET /api/user/favorites/{projectId}/exists
        [HttpGet("{projectId}/exists")]
        public async Task<IActionResult> Exists(string projectId)
        {
            var userId     = GetUserId();
            var favorited  = await _dataRepo.IsFavoritedAsync(userId, projectId);
            return Ok(new { exists = favorited });
        }

        private Guid GetUserId() =>
            Guid.Parse(User.FindFirstValue(ClaimTypes.NameIdentifier)
                ?? User.FindFirstValue("sub")!);
    }

    public record AddFavoriteRequest(string ProjectId);
}
