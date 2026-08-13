using HyderabadUrbanReality.Core.Interfaces;
using HyderabadUrbanReality.Infrastructure.Repositories;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using System.Text.RegularExpressions;

namespace HyderabadUrbanReality.Controllers
{
    /// <summary>
    /// Schedule site-visit requests:
    /// POST /api/schedule-visit          — public
    /// GET  /api/admin/schedule-visits   — admin only
    /// PUT  /api/admin/schedule-visits/{id}/status — admin only
    /// DELETE /api/admin/schedule-visits/{id}       — admin only
    /// </summary>
    [ApiController]
    public class ScheduleVisitController : ControllerBase
    {
        private readonly ScheduleVisitRepository _visitRepo;
        private readonly IEmailService _email;
        private readonly IInputSanitizer _sanitizer;
        private readonly ILogger<ScheduleVisitController> _logger;

        public ScheduleVisitController(
            ScheduleVisitRepository visitRepo,
            IEmailService email,
            IInputSanitizer sanitizer,
            ILogger<ScheduleVisitController> logger)
        {
            _visitRepo = visitRepo;
            _email     = email;
            _sanitizer = sanitizer;
            _logger    = logger;
        }

        // ── POST /api/schedule-visit ─────────────────────────────────────
        [HttpPost("api/schedule-visit")]
        [AllowAnonymous]
        public async Task<IActionResult> ScheduleVisit([FromBody] ScheduleVisitRequest dto)
        {
            // Validate required fields
            if (string.IsNullOrWhiteSpace(dto.Name)      ||
                string.IsNullOrWhiteSpace(dto.Email)     ||
                string.IsNullOrWhiteSpace(dto.Mobile)    ||
                string.IsNullOrWhiteSpace(dto.VisitDate) ||
                string.IsNullOrWhiteSpace(dto.VisitTime))
                return BadRequest(new { error = "all_fields_required" });

            if (!Regex.IsMatch(dto.Email, @"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"))
                return BadRequest(new { error = "invalid_email" });

            if (!Regex.IsMatch(dto.Mobile, @"^\d{10}$"))
                return BadRequest(new { error = "invalid_mobile", message = "Mobile must be 10 digits" });

            if (!DateOnly.TryParse(dto.VisitDate, out var parsedDate))
                return BadRequest(new { error = "invalid_date", message = "visitDate must be YYYY-MM-DD" });

            if (parsedDate < DateOnly.FromDateTime(DateTime.UtcNow.Date))
                return BadRequest(new { error = "date_in_past", message = "Visit date cannot be in the past" });

            var visit = new ScheduleVisit
            {
                ProjectId        = dto.ProjectId is not null ? _sanitizer.Sanitize(dto.ProjectId) : null,
                ProjectName      = dto.ProjectName is not null ? _sanitizer.Sanitize(dto.ProjectName) : null,
                Name             = _sanitizer.Sanitize(dto.Name),
                Email            = _sanitizer.Sanitize(dto.Email).ToLowerInvariant(),
                Mobile           = _sanitizer.Sanitize(dto.Mobile),
                VisitDate        = parsedDate,
                VisitTime        = _sanitizer.Sanitize(dto.VisitTime),
                Message          = dto.Message is not null ? _sanitizer.Sanitize(dto.Message) : null,
                LocationAddress  = dto.LocationAddress is not null ? _sanitizer.Sanitize(dto.LocationAddress) : null,
                LocationLat      = dto.LocationLat,
                LocationLng      = dto.LocationLng,
                LocationMapUrl   = dto.LocationMapUrl is not null ? _sanitizer.Sanitize(dto.LocationMapUrl) : null
            };

            var insertedId = await _visitRepo.InsertAsync(visit);
            _logger.LogInformation("Visit {Id} scheduled for project {Project} by {Email} on {Date}",
                insertedId, visit.ProjectName ?? visit.ProjectId, visit.Email, visit.VisitDate);

            // Send email notifications (admin + visitor confirmation) — non-blocking
            try
            {
                await _email.SendVisitNotificationAsync(
                    visit.Name, visit.Email, visit.Mobile,
                    visit.ProjectName ?? visit.ProjectId ?? "General Enquiry",
                    visit.VisitDate.ToString("dddd, dd MMM yyyy"),
                    visit.VisitTime,
                    visit.Message);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to send visit notification email for visit {Id}", insertedId);
            }

            return StatusCode(201, new
            {
                message = "Visit scheduled successfully. We will contact you to confirm.",
                id      = insertedId
            });
        }

        // ── GET /api/admin/schedule-visits ────────────────────────────────
        [HttpGet("api/admin/schedule-visits")]
        [Authorize]
        public async Task<IActionResult> GetAll([FromQuery] int page = 1, [FromQuery] int pageSize = 50)
        {
            var visits = await _visitRepo.GetAllAsync(page, pageSize);
            return Ok(visits.Select(v => new
            {
                v.Id, v.ProjectId, v.ProjectName, v.Name, v.Email, v.Mobile,
                visitDate       = v.VisitDate.ToString("yyyy-MM-dd"),
                v.VisitTime, v.Message, v.Status,
                v.LocationAddress, v.LocationLat, v.LocationLng, v.LocationMapUrl,
                createdAt = v.CreatedAt
            }));
        }

        // ── PUT /api/admin/schedule-visits/{id}/status ────────────────────
        [HttpPut("api/admin/schedule-visits/{visitId:int}/status")]
        [Authorize]
        public async Task<IActionResult> UpdateStatus(int visitId, [FromBody] UpdateVisitStatusRequest dto)
        {
            var allowed = new[] { "pending", "confirmed", "cancelled" };
            if (!allowed.Contains(dto.Status))
                return BadRequest(new { error = "invalid_status", message = "Status must be: pending, confirmed or cancelled" });

            var ok = await _visitRepo.UpdateStatusAsync(visitId, dto.Status);
            if (!ok) return NotFound(new { error = "not_found" });
            return Ok(new { message = $"Visit status updated to '{dto.Status}'" });
        }

        // ── DELETE /api/admin/schedule-visits/{id} ────────────────────────
        [HttpDelete("api/admin/schedule-visits/{visitId:int}")]
        [Authorize]
        public async Task<IActionResult> Delete(int visitId)
        {
            var ok = await _visitRepo.DeleteAsync(visitId);
            if (!ok) return NotFound(new { error = "not_found" });
            return NoContent();
        }
    }

    public record ScheduleVisitRequest(
        string Name,
        string Email,
        string Mobile,
        string VisitDate,
        string VisitTime,
        string? ProjectId,
        string? ProjectName,
        string? Message,
        string? LocationAddress,
        double? LocationLat,
        double? LocationLng,
        string? LocationMapUrl
    );

    public record UpdateVisitStatusRequest(string Status);
}
