using HyderabadUrbanReality.Core.Interfaces;
using HyderabadUrbanReality.Infrastructure.Repositories;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace HyderabadUrbanReality.Controllers
{
    /// <summary>
    /// Property media management: images, documents, floor plans, YouTube videos.
    /// GET endpoints are public. POST/PUT/DELETE require admin.
    /// </summary>
    [ApiController]
    [Route("api/projects/{projectId}/media")]
    public class MediaController : ControllerBase
    {
        private readonly MediaRepository _media;
        private readonly IProjectRepository _projects;
        private readonly IWebHostEnvironment _env;
        private readonly ILogger<MediaController> _logger;
        private readonly IFileService _fileService;
        private readonly IConfiguration _config;

        private static readonly HashSet<string> AllowedImageTypes =
            new(StringComparer.OrdinalIgnoreCase) { "image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif" };

        private static readonly HashSet<string> AllowedDocTypes =
            new(StringComparer.OrdinalIgnoreCase) { "application/pdf", "application/msword",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document" };

        private const long MaxImageSize = 10 * 1024 * 1024;   // 10 MB
        private const long MaxDocSize   = 50 * 1024 * 1024;   // 50 MB

        public MediaController(
            MediaRepository media,
            IProjectRepository projects,
            IWebHostEnvironment env,
            IFileService fileService,
            IConfiguration config,
            ILogger<MediaController> logger)
        {
            _media       = media;
            _projects    = projects;
            _env         = env;
            _fileService = fileService;
            _config      = config;
            _logger      = logger;
        }

        // ── GET /api/projects/{id}/media ──────────────────────────────────────
        [HttpGet]
        public async Task<IActionResult> GetAll(string projectId, [FromQuery] string? type = null)
        {
            var items = await _media.GetByProjectAsync(projectId, type);
            return Ok(items);
        }

        // ── POST /api/projects/{id}/media/upload ──────────────────────────────
        // Upload image, document, or floor plan
        [HttpPost("upload")]
        [Authorize]
        [RequestSizeLimit(55 * 1024 * 1024)]
        public async Task<IActionResult> Upload(string projectId, [FromForm] IFormFile file,
            [FromForm] string mediaType = "image", [FromForm] string? title = null, [FromForm] int sortOrder = 0)
        {
            if (!await _projects.ProjectExistsAsync(projectId))
                return NotFound(new { error = "project_not_found" });

            if (file == null || file.Length == 0)
                return BadRequest(new { error = "no_file" });

            var mime = file.ContentType.ToLower();

            // Validate type + size
            if (mediaType == "image" || mediaType == "floorplan")
            {
                if (!AllowedImageTypes.Contains(mime))
                    return BadRequest(new { error = "invalid_type", message = "Only JPEG, PNG, WebP, GIF allowed" });
                if (file.Length > MaxImageSize)
                    return BadRequest(new { error = "file_too_large", message = "Max 10 MB" });
            }
            else if (mediaType == "document")
            {
                if (!AllowedDocTypes.Contains(mime))
                    return BadRequest(new { error = "invalid_type", message = "Only PDF and Word docs allowed" });
                if (file.Length > MaxDocSize)
                    return BadRequest(new { error = "file_too_large", message = "Max 25 MB" });
            }
            else
            {
                return BadRequest(new { error = "invalid_media_type", message = "Use 'image', 'floorplan', or 'document'" });
            }

            string fileUrl;
            var ext      = Path.GetExtension(file.FileName);
            var safeName = $"{Guid.NewGuid()}{ext}";

            // Try Supabase Storage first; fall back to local disk if not configured
            var supabaseUrl = _config["SupabaseSettings:Url"];
            var serviceKey  = _config["SupabaseSettings:ServiceKey"];

            if (!string.IsNullOrEmpty(supabaseUrl) && !string.IsNullOrEmpty(serviceKey))
            {
                // Upload to Supabase Storage — persistent across redeploys
                try
                {
                    await using var stream = file.OpenReadStream();
                    fileUrl = await _fileService.UploadFileAsync(stream, safeName);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Supabase Storage upload failed for {File}", safeName);
                    return StatusCode(500, new { error = "upload_failed", message = ex.Message });
                }
            }
            else
            {
                // Fallback: local disk (dev only — not persistent on Render)
                var uploadRoot = Path.Combine(_env.ContentRootPath, "uploads", "properties", SanitizeId(projectId), mediaType + "s");
                Directory.CreateDirectory(uploadRoot);
                var filePath = Path.Combine(uploadRoot, safeName);
                await using (var stream = new FileStream(filePath, FileMode.Create))
                    await file.CopyToAsync(stream);
                fileUrl = $"/media/properties/{SanitizeId(projectId)}/{mediaType}s/{safeName}";
            }

            var displayTitle = title ?? Path.GetFileNameWithoutExtension(file.FileName);
            var id = await _media.AddAsync(projectId, mediaType, displayTitle, fileUrl, safeName, file.Length, mime, sortOrder);
            _logger.LogInformation("Uploaded {Type} for project {Project}: {Url}", mediaType, projectId, fileUrl);

            return StatusCode(201, new { id, url = fileUrl, title = displayTitle, mediaType, fileSize = file.Length });
        }

        // ── POST /api/projects/{id}/media/video ───────────────────────────────
        // Add YouTube video URL
        [HttpPost("video")]
        [Authorize]
        public async Task<IActionResult> AddVideo(string projectId, [FromBody] AddVideoRequest dto)
        {
            if (!await _projects.ProjectExistsAsync(projectId))
                return NotFound(new { error = "project_not_found" });

            if (string.IsNullOrWhiteSpace(dto.Url))
                return BadRequest(new { error = "url_required" });

            // Validate YouTube URL
            if (!dto.Url.Contains("youtube.com") && !dto.Url.Contains("youtu.be"))
                return BadRequest(new { error = "invalid_url", message = "Only YouTube URLs are supported" });

            var id = await _media.AddAsync(projectId, "video", dto.Title ?? "Video Tour", dto.Url, null, null, "video/youtube", dto.SortOrder);
            return StatusCode(201, new { id, url = dto.Url, title = dto.Title ?? "Video Tour", mediaType = "video" });
        }

        // ── PUT /api/projects/{id}/media/{mediaId} ────────────────────────────
        [HttpPut("{mediaId:guid}")]
        [Authorize]
        public async Task<IActionResult> Update(string projectId, Guid mediaId, [FromBody] UpdateMediaRequest dto)
        {
            var item = await _media.GetByIdAsync(mediaId);
            if (item is null) return NotFound(new { error = "not_found" });

            var ok = await _media.UpdateAsync(mediaId, dto.Title ?? "", dto.SortOrder);
            if (!ok) return NotFound(new { error = "not_found" });
            return Ok(new { message = "Updated" });
        }

        // ── DELETE /api/projects/{id}/media/{mediaId} ─────────────────────────
        [HttpDelete("{mediaId:guid}")]
        [Authorize]
        public async Task<IActionResult> Delete(string projectId, Guid mediaId)
        {
            var fileName = await _media.DeleteAsync(mediaId);
            if (fileName == null) return NotFound(new { error = "not_found" });

            // Delete physical file if it exists
            if (!string.IsNullOrEmpty(fileName))
            {
                var uploadRoot = Path.Combine(_env.ContentRootPath, "uploads", "properties", SanitizeId(projectId));
                foreach (var sub in new[] { "images", "floorplans", "documents" })
                {
                    var fp = Path.Combine(uploadRoot, sub, fileName);
                    if (System.IO.File.Exists(fp)) { System.IO.File.Delete(fp); break; }
                }
            }

            return NoContent();
        }

        private static string SanitizeId(string id) =>
            System.Text.RegularExpressions.Regex.Replace(id, @"[^a-zA-Z0-9\-_]", "_");

        // ── GET /api/projects/{id}/media/{mediaId}/download ──────────────────
        // Streams a stored document file back to the browser as a download
        [HttpGet("{mediaId:guid}/download")]
        [AllowAnonymous]
        public async Task<IActionResult> Download(string projectId, Guid mediaId)
        {
            var item = await _media.GetByIdAsync(mediaId);
            if (item is null) return NotFound(new { error = "not_found" });

            var itemDict = (IDictionary<string, object?>)item;
            var fileName  = itemDict.TryGetValue("file_name",  out var fn) ? fn?.ToString() : null;
            var mediaType = itemDict.TryGetValue("media_type", out var mt) ? mt?.ToString() : null;
            var title     = itemDict.TryGetValue("title",      out var tt) ? tt?.ToString() : fileName;
            var mimeType  = itemDict.TryGetValue("mime_type",  out var mm) ? mm?.ToString() : "application/octet-stream";

            if (string.IsNullOrEmpty(fileName))
                return BadRequest(new { error = "no_file", message = "This media item has no downloadable file." });

            var typeFolder = (mediaType ?? "document") + "s";
            var uploadRoot = Path.Combine(_env.ContentRootPath, "uploads", "properties",
                                          SanitizeId(projectId), typeFolder);
            var filePath   = Path.GetFullPath(Path.Combine(uploadRoot, fileName));

            // Prevent path traversal
            var expectedBase = Path.GetFullPath(uploadRoot);
            if (!filePath.StartsWith(expectedBase, StringComparison.OrdinalIgnoreCase))
                return BadRequest(new { error = "invalid_path" });

            if (!System.IO.File.Exists(filePath))
                return NotFound(new { error = "file_not_found" });

            var downloadName = Path.HasExtension(title ?? "")
                ? title!
                : title + Path.GetExtension(fileName);

            _logger.LogInformation("Download: project={Project} file={File}", projectId, fileName);

            var stream = new FileStream(filePath, FileMode.Open, FileAccess.Read, FileShare.Read);
            return File(stream, mimeType ?? "application/octet-stream",
                        downloadName, enableRangeProcessing: true);
        }

        // ── POST /api/projects/{id}/media/register-scraped ────────────────────
        // Register an already-scraped floor plan page URL in project_media without re-uploading
        [HttpPost("register-scraped")]
        [Authorize]
        public async Task<IActionResult> RegisterScraped(string projectId, [FromBody] RegisterScrapedRequest dto)
        {
            if (!await _projects.ProjectExistsAsync(projectId))
                return NotFound(new { error = "project_not_found" });

            if (string.IsNullOrWhiteSpace(dto.FileUrl))
                return BadRequest(new { error = "file_url_required" });

            var allowedTypes = new[] { "image", "floorplan", "document" };
            if (!allowedTypes.Contains(dto.MediaType))
                return BadRequest(new { error = "invalid_media_type" });

            var title = dto.Title ?? Path.GetFileNameWithoutExtension(dto.FileUrl.Split('/').Last());
            var id = await _media.AddAsync(projectId, dto.MediaType, title, dto.FileUrl, null, null, "image/png", dto.SortOrder);
            _logger.LogInformation("Registered scraped page for project {Project}: {Url}", projectId, dto.FileUrl);
            return StatusCode(201, new { id, url = dto.FileUrl, title, mediaType = dto.MediaType });
        }
    }

    public record AddVideoRequest(string Url, string? Title = null, int SortOrder = 0);
    public record UpdateMediaRequest(string? Title = null, int SortOrder = 0);
    public record RegisterScrapedRequest(string FileUrl, string? Title = null, string MediaType = "floorplan", int SortOrder = 0);
}
