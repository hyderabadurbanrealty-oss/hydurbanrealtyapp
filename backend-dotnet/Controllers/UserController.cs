using HyderabadUrbanReality.Core.DTOs;
using HyderabadUrbanReality.Core.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using System.Security.Claims;

namespace HyderabadUrbanReality.Controllers
{
    /// <summary>
    /// User profile management endpoints.
    /// All endpoints require a valid JWT (Req 17.1–17.3).
    /// </summary>
    [ApiController]
    [Route("api/user")]
    [Authorize]
    public class UserController : ControllerBase
    {
        private readonly IUserRepository _userRepo;
        private readonly IInputSanitizer _sanitizer;
        private readonly ILogger<UserController> _logger;

        public UserController(
            IUserRepository userRepo,
            IInputSanitizer sanitizer,
            ILogger<UserController> logger)
        {
            _userRepo  = userRepo;
            _sanitizer = sanitizer;
            _logger    = logger;
        }

        // ── GET /api/user/profile ─────────────────────────────────────────────

        [HttpGet("profile")]
        public async Task<IActionResult> GetProfile()
        {
            var userId = GetUserId();
            var user   = await _userRepo.GetByIdAsync(userId);
            if (user is null) return NotFound();

            return Ok(new UserProfileDto(
                user.Id, user.FullName, user.Email, user.Mobile,
                user.AvatarUrl, user.IsVerified, user.CreatedAt, user.Role ?? "user"));
        }

        // ── PUT /api/user/profile ─────────────────────────────────────────────

        [HttpPut("profile")]
        public async Task<IActionResult> UpdateProfile([FromBody] UpdateProfileRequestDto dto)
        {
            var userId = GetUserId();
            var user   = await _userRepo.GetByIdAsync(userId);
            if (user is null) return NotFound();

            // Apply sanitizer (Req 12.6, 18.6)
            if (dto.FullName is not null)  user.FullName  = _sanitizer.Sanitize(dto.FullName);
            if (dto.Mobile   is not null)  user.Mobile    = _sanitizer.Sanitize(dto.Mobile);
            if (dto.AvatarUrl is not null) user.AvatarUrl = dto.AvatarUrl;

            await _userRepo.UpdateAsync(user);
            return Ok(new UserProfileDto(
                user.Id, user.FullName, user.Email, user.Mobile,
                user.AvatarUrl, user.IsVerified, user.CreatedAt, user.Role ?? "user"));
        }

        // ── PUT /api/user/change-password ─────────────────────────────────────

        [HttpPut("change-password")]
        public async Task<IActionResult> ChangePassword([FromBody] ChangePasswordRequestDto dto)
        {
            var userId = GetUserId();
            var user   = await _userRepo.GetByIdAsync(userId);
            if (user is null) return NotFound();

            if (!BCrypt.Net.BCrypt.Verify(dto.CurrentPassword, user.PasswordHash))
                return BadRequest(new { error = "incorrect_current_password" });

            user.PasswordHash = BCrypt.Net.BCrypt.HashPassword(dto.NewPassword, workFactor: 12);
            await _userRepo.UpdateAsync(user);
            return Ok(new { message = "Password changed successfully." });
        }

        // ── DELETE /api/user/account ──────────────────────────────────────────

        /// <summary>Soft-delete: sets is_active=false and revokes all refresh tokens (Req 12.5).</summary>
        [HttpDelete("account")]
        public async Task<IActionResult> DeleteAccount()
        {
            var userId = GetUserId();
            var user   = await _userRepo.GetByIdAsync(userId);
            if (user is null) return NotFound();

            user.IsActive = false;
            await _userRepo.UpdateAsync(user);
            await _userRepo.RevokeAllRefreshTokensForUserAsync(userId);

            return Ok(new { message = "Account deactivated." });
        }

        // ── Helpers ───────────────────────────────────────────────────────────

        private Guid GetUserId() =>
            Guid.Parse(User.FindFirstValue(ClaimTypes.NameIdentifier)
                ?? User.FindFirstValue("sub")
                ?? throw new InvalidOperationException("User ID claim missing"));
    }
}
