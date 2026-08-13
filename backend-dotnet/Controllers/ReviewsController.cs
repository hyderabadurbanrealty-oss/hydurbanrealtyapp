using HyderabadUrbanReality.Core.Interfaces;
using HyderabadUrbanReality.Infrastructure.Repositories;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using System.Text.RegularExpressions;

namespace HyderabadUrbanReality.Controllers
{
    /// <summary>
    /// Property reviews: public submission + admin approval/listing.
    /// POST /api/projects/{id}/reviews  — public (rate-limited via global rule)
    /// GET  /api/projects/{id}/reviews  — public (returns approved reviews only)
    /// GET  /api/admin/reviews          — admin only
    /// PUT  /api/admin/reviews/{id}/approve — admin only
    /// DELETE /api/admin/reviews/{id}   — admin only
    /// </summary>
    [ApiController]
    public class ReviewsController : ControllerBase
    {
        private readonly ReviewRepository _reviewRepo;
        private readonly IEmailService _email;
        private readonly IInputSanitizer _sanitizer;
        private readonly IProjectRepository _projectRepo;
        private readonly ILogger<ReviewsController> _logger;

        public ReviewsController(
            ReviewRepository reviewRepo,
            IEmailService email,
            IInputSanitizer sanitizer,
            IProjectRepository projectRepo,
            ILogger<ReviewsController> logger)
        {
            _reviewRepo  = reviewRepo;
            _email       = email;
            _sanitizer   = sanitizer;
            _projectRepo = projectRepo;
            _logger      = logger;
        }

        // ── GET /api/projects/{id}/reviews ────────────────────────────────
        [HttpGet("api/projects/{id}/reviews")]
        [AllowAnonymous]
        public async Task<IActionResult> GetReviews(string id)
        {
            var reviews = await _reviewRepo.GetApprovedByProjectAsync(id);
            var result = reviews.Select(r => new
            {
                r.Id,
                r.Name,
                rating    = r.Rating,
                review    = r.ReviewText,
                date      = r.CreatedAt,
                verified  = true
            });
            return Ok(result);
        }

        // ── POST /api/projects/{id}/reviews ───────────────────────────────
        [HttpPost("api/projects/{id}/reviews")]
        [AllowAnonymous]
        public async Task<IActionResult> SubmitReview(string id, [FromBody] SubmitReviewRequest dto)
        {
            // Validate
            if (string.IsNullOrWhiteSpace(dto.Name)    ||
                string.IsNullOrWhiteSpace(dto.Email)   ||
                string.IsNullOrWhiteSpace(dto.Contact) ||
                string.IsNullOrWhiteSpace(dto.Review))
                return BadRequest(new { error = "all_fields_required" });

            if (!Regex.IsMatch(dto.Email, @"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"))
                return BadRequest(new { error = "invalid_email" });

            if (!Regex.IsMatch(dto.Contact, @"^\d{10}$"))
                return BadRequest(new { error = "invalid_contact", message = "Contact must be 10 digits" });

            if (dto.Rating < 1 || dto.Rating > 5)
                return BadRequest(new { error = "invalid_rating", message = "Rating must be 1–5" });

            var review = new Review
            {
                ProjectId  = _sanitizer.Sanitize(id),
                Name       = _sanitizer.Sanitize(dto.Name),
                Email      = _sanitizer.Sanitize(dto.Email).ToLowerInvariant(),
                Contact    = _sanitizer.Sanitize(dto.Contact),
                Rating     = dto.Rating,
                ReviewText = _sanitizer.Sanitize(dto.Review)
            };

            var insertedId = await _reviewRepo.InsertAsync(review);
            _logger.LogInformation("Review {Id} submitted for project {Project} by {Email}", insertedId, id, review.Email);

            // Resolve project name for the email subject
            var projectName = id;
            try
            {
                var project = await _projectRepo.GetProjectByIdAsync(id);
                if (project is not null &&
                    project.TryGetValue("Project Name", out var pn))
                    projectName = pn?.ToString() ?? id;
            }
            catch { /* swallow — project name is cosmetic */ }

            // Notify admin (non-blocking — failure must not fail the request)
            try
            {
                await _email.SendReviewNotificationAsync(projectName, review.Name, review.Email, review.Rating, review.ReviewText);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to send review notification email for review {Id}", insertedId);
            }

            return StatusCode(201, new
            {
                message = "Your review has been submitted and is pending approval.",
                id      = insertedId
            });
        }

        // ── GET /api/admin/reviews ─────────────────────────────────────────
        [HttpGet("api/admin/reviews")]
        [Authorize]
        public async Task<IActionResult> GetAllReviews([FromQuery] int page = 1, [FromQuery] int pageSize = 50)
        {
            var reviews = await _reviewRepo.GetAllAsync(page, pageSize);
            return Ok(reviews.Select(r => new
            {
                r.Id, r.ProjectId, r.Name, r.Email, r.Contact,
                rating   = r.Rating,
                review   = r.ReviewText,
                r.IsApproved,
                date     = r.CreatedAt
            }));
        }

        // ── PUT /api/admin/reviews/{id}/approve ───────────────────────────
        [HttpPut("api/admin/reviews/{reviewId:int}/approve")]
        [Authorize]
        public async Task<IActionResult> ApproveReview(int reviewId)
        {
            var ok = await _reviewRepo.ApproveAsync(reviewId);
            if (!ok) return NotFound(new { error = "not_found" });
            return Ok(new { message = "Review approved" });
        }

        // ── DELETE /api/admin/reviews/{id} ────────────────────────────────
        [HttpDelete("api/admin/reviews/{reviewId:int}")]
        [Authorize]
        public async Task<IActionResult> DeleteReview(int reviewId)
        {
            var ok = await _reviewRepo.DeleteAsync(reviewId);
            if (!ok) return NotFound(new { error = "not_found" });
            return NoContent();
        }
    }

    public record SubmitReviewRequest(
        string Name,
        string Email,
        string Contact,
        int Rating,
        string Review
    );
}
