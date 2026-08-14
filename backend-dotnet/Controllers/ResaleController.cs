using Dapper;
using HyderabadUrbanReality.Core.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Npgsql;
using System.Security.Claims;
using System.Text.Json;

namespace HyderabadUrbanReality.Controllers
{
    [ApiController]
    [Route("api/resale")]
    public class ResaleController : ControllerBase
    {
        private readonly IConfiguration _config;
        private readonly IFileService   _fileService;
        private readonly ILogger<ResaleController> _logger;

        private string ConnStr => _config.GetConnectionString("DefaultConnection")!;

        private static readonly HashSet<string> AllowedImageTypes =
            new(StringComparer.OrdinalIgnoreCase)
            { "image/jpeg", "image/jpg", "image/png", "image/webp" };

        private const long MaxImageSize = 10 * 1024 * 1024; // 10 MB

        public ResaleController(IConfiguration config, IFileService fileService,
            ILogger<ResaleController> logger)
        {
            _config      = config;
            _fileService = fileService;
            _logger      = logger;
        }

        // ── POST /api/resale ─────────────────────────────────────────────────
        // Submit a new resale listing (authenticated, multipart/form-data)
        [HttpPost]
        [Authorize]
        [RequestSizeLimit(55 * 1024 * 1024)]
        public async Task<IActionResult> Submit([FromForm] ResaleSubmitRequest dto,
            [FromForm] List<IFormFile>? images)
        {
            if (string.IsNullOrWhiteSpace(dto.OwnerName))
                return BadRequest(new { error = "owner_name_required" });
            if (string.IsNullOrWhiteSpace(dto.ContactPhone))
                return BadRequest(new { error = "contact_phone_required" });

            var userId = GetUserId();
            var listingId = Guid.NewGuid();

            // Upload images to Supabase Storage (max 5)
            var imageUrls = new List<string>();
            var files = images?.Take(5).ToList() ?? new List<IFormFile>();
            foreach (var file in files)
            {
                if (file.Length == 0) continue;
                if (!AllowedImageTypes.Contains(file.ContentType.ToLower()))
                    return BadRequest(new { error = "invalid_image_type", message = "Only JPEG, PNG, WebP allowed" });
                if (file.Length > MaxImageSize)
                    return BadRequest(new { error = "image_too_large", message = "Max 10 MB per image" });

                var ext      = Path.GetExtension(file.FileName);
                var safeName = $"{Guid.NewGuid()}{ext}";
                try
                {
                    await using var stream = file.OpenReadStream();
                    var url = await _fileService.UploadFileAsync(stream, $"resale-{listingId}-{safeName}");
                    imageUrls.Add(url);
                }
                catch (Exception ex)
                {
                    _logger.LogWarning(ex, "Failed to upload resale image {File}", safeName);
                }
            }

            // Parse features JSON array
            List<string> featureList;
            try { featureList = string.IsNullOrWhiteSpace(dto.FeaturesJson)
                ? new List<string>()
                : JsonSerializer.Deserialize<List<string>>(dto.FeaturesJson) ?? new List<string>(); }
            catch { featureList = new List<string>(); }

            await using var conn = new NpgsqlConnection(ConnStr);
            var sql = @"
                INSERT INTO resale_listings (
                    id, user_id, owner_name, residence_type, contact_phone, contact_email,
                    builder_name, project_name, location, configuration,
                    super_built_up_area, age_of_property, expected_price, preferred_callback,
                    features, images, status
                ) VALUES (
                    @id, @userId, @ownerName, @residenceType, @contactPhone, @contactEmail,
                    @builderName, @projectName, @location, @configuration,
                    @superBuiltUpArea, @ageOfProperty, @expectedPrice, @preferredCallback,
                    @features::jsonb, @images::jsonb, 'pending'
                ) RETURNING id";

            var insertedId = await conn.ExecuteScalarAsync<Guid>(sql, new
            {
                id               = listingId,
                userId,
                ownerName        = dto.OwnerName.Trim(),
                residenceType    = dto.ResidenceType ?? "india",
                contactPhone     = dto.ContactPhone.Trim(),
                contactEmail     = dto.ContactEmail?.Trim(),
                builderName      = dto.BuilderName?.Trim(),
                projectName      = dto.ProjectName?.Trim(),
                location         = dto.Location?.Trim(),
                configuration    = dto.Configuration?.Trim(),
                superBuiltUpArea = dto.SuperBuiltUpArea,
                ageOfProperty    = dto.AgeOfProperty?.Trim(),
                expectedPrice    = dto.ExpectedPrice,
                preferredCallback = dto.PreferredCallback?.Trim(),
                features         = JsonSerializer.Serialize(featureList),
                images           = JsonSerializer.Serialize(imageUrls)
            });

            _logger.LogInformation("Resale listing {Id} submitted by user {User}", insertedId, userId);
            return StatusCode(201, new { id = insertedId, message = "Listing submitted successfully." });
        }

        // ── GET /api/resale/my ───────────────────────────────────────────────
        [HttpGet("my")]
        [Authorize]
        public async Task<IActionResult> GetMy([FromQuery] int page = 1, [FromQuery] int pageSize = 20)
        {
            var userId = GetUserId();
            await using var conn = new NpgsqlConnection(ConnStr);
            var listings = await conn.QueryAsync<dynamic>(
                @"SELECT id, owner_name, residence_type, contact_phone, contact_email,
                         builder_name, project_name, location, configuration,
                         super_built_up_area, age_of_property, expected_price, preferred_callback,
                         features, images, status, admin_notes, created_at, updated_at
                  FROM resale_listings
                  WHERE user_id = @userId
                  ORDER BY created_at DESC
                  LIMIT @pageSize OFFSET @offset",
                new { userId, pageSize, offset = (page - 1) * pageSize });
            var total = await conn.ExecuteScalarAsync<int>(
                "SELECT COUNT(*) FROM resale_listings WHERE user_id = @userId", new { userId });
            return Ok(new { listings, total, page, pageSize });
        }

        // ── DELETE /api/resale/{id} ──────────────────────────────────────────
        [HttpDelete("{id:guid}")]
        [Authorize]
        public async Task<IActionResult> Delete(Guid id)
        {
            var userId = GetUserId();
            await using var conn = new NpgsqlConnection(ConnStr);
            var affected = await conn.ExecuteAsync(
                "DELETE FROM resale_listings WHERE id = @id AND user_id = @userId",
                new { id, userId });
            if (affected == 0) return NotFound(new { error = "not_found" });
            return NoContent();
        }

        // ── GET /api/admin/resale ────────────────────────────────────────────
        [HttpGet("/api/admin/resale")]
        [Authorize]
        public async Task<IActionResult> AdminGetAll(
            [FromQuery] int page = 1, [FromQuery] int pageSize = 50,
            [FromQuery] string? status = null)
        {
            await using var conn = new NpgsqlConnection(ConnStr);
            var where = status != null ? "WHERE status = @status" : "";
            var listings = await conn.QueryAsync<dynamic>(
                $@"SELECT r.*, u.email AS user_email, u.full_name AS user_full_name
                   FROM resale_listings r
                   LEFT JOIN users u ON u.id = r.user_id
                   {where}
                   ORDER BY r.created_at DESC
                   LIMIT @pageSize OFFSET @offset",
                new { status, pageSize, offset = (page - 1) * pageSize });
            var total = await conn.ExecuteScalarAsync<int>(
                $"SELECT COUNT(*) FROM resale_listings {where}", new { status });
            return Ok(new { listings, total, page, pageSize });
        }

        // ── PUT /api/admin/resale/{id}/status ────────────────────────────────
        [HttpPut("/api/admin/resale/{id:guid}/status")]
        [Authorize]
        public async Task<IActionResult> AdminUpdateStatus(Guid id, [FromBody] UpdateResaleStatusDto dto)
        {
            var allowed = new[] { "pending", "active", "sold", "rejected" };
            if (!allowed.Contains(dto.Status))
                return BadRequest(new { error = "invalid_status" });

            await using var conn = new NpgsqlConnection(ConnStr);
            var affected = await conn.ExecuteAsync(
                @"UPDATE resale_listings
                  SET status = @status, admin_notes = @adminNotes, updated_at = NOW()
                  WHERE id = @id",
                new { id, status = dto.Status, adminNotes = dto.AdminNotes });
            if (affected == 0) return NotFound(new { error = "not_found" });
            return Ok(new { message = $"Status updated to '{dto.Status}'" });
        }

        private Guid? GetUserId()
        {
            var claim = User.FindFirstValue(ClaimTypes.NameIdentifier)
                     ?? User.FindFirstValue("sub");
            return claim != null && Guid.TryParse(claim, out var id) ? id : null;
        }
    }

    public class ResaleSubmitRequest
    {
        public string  OwnerName         { get; set; } = "";
        public string  ResidenceType     { get; set; } = "india";
        public string  ContactPhone      { get; set; } = "";
        public string? ContactEmail      { get; set; }
        public string? BuilderName       { get; set; }
        public string? ProjectName       { get; set; }
        public string? Location          { get; set; }
        public string? Configuration     { get; set; }
        public decimal? SuperBuiltUpArea { get; set; }
        public string? AgeOfProperty     { get; set; }
        public long?   ExpectedPrice     { get; set; }
        public string? PreferredCallback { get; set; }
        public string? FeaturesJson      { get; set; }  // JSON array of feature strings
    }

    public record UpdateResaleStatusDto(string Status, string? AdminNotes = null);
}
