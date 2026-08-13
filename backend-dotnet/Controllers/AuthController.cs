using HyderabadUrbanReality.Core.DTOs;
using HyderabadUrbanReality.Core.Entities;
using HyderabadUrbanReality.Core.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.IdentityModel.Tokens;
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Security.Cryptography;
using System.Text;

namespace HyderabadUrbanReality.Controllers
{
    /// <summary>
    /// Handles user authentication: registration, email verification, login,
    /// token refresh, logout, and password reset flows.
    /// </summary>
    [ApiController]
    [Route("api/auth")]
    public class AuthController : ControllerBase
    {
        private readonly IUserRepository _userRepo;
        private readonly IEmailService _emailService;
        private readonly IInputSanitizer _sanitizer;
        private readonly IConfiguration _config;
        private readonly ILogger<AuthController> _logger;

        public AuthController(
            IUserRepository userRepo,
            IEmailService emailService,
            IInputSanitizer sanitizer,
            IConfiguration config,
            ILogger<AuthController> logger)
        {
            _userRepo     = userRepo;
            _emailService = emailService;
            _sanitizer    = sanitizer;
            _config       = config;
            _logger       = logger;
        }

        // ── POST /api/auth/register ───────────────────────────────────────────

        /// <summary>
        /// Register a new user account.
        /// Returns 409 if email already exists, 201 on success.
        /// Email delivery failure does NOT prevent registration (Req 7.5).
        /// </summary>
        [HttpPost("register")]
        [AllowAnonymous]
        public async Task<IActionResult> Register([FromBody] RegisterRequestDto dto)
        {
            if (!ModelState.IsValid)
                return BadRequest(ModelState);

            // Check for duplicate email (Req 7.3)
            if (await _userRepo.EmailExistsAsync(dto.Email.ToLowerInvariant()))
            {
                return Conflict(new { error = "email_already_exists", message = "An account with this email already exists." });
            }

            // Hash password with BCrypt cost factor 12 (Req 7.2)
            var passwordHash = BCrypt.Net.BCrypt.HashPassword(dto.Password, workFactor: 12);

            // Sanitize user-supplied strings (Req 7.6)
            var fullName = _sanitizer.Sanitize(dto.FullName);
            var mobile   = dto.Mobile is not null ? _sanitizer.Sanitize(dto.Mobile) : null;

            var user = new User
            {
                Id           = Guid.NewGuid(),
                Email        = dto.Email.ToLowerInvariant(),
                PasswordHash = passwordHash,
                FullName     = fullName,
                Mobile       = mobile,
                IsVerified   = false,   // requires email verification (Req 7.1)
                IsActive     = true,
                Role         = "user",
            };

            var created = await _userRepo.CreateAsync(user);

            // Generate email verification token (Req 7.4)
            var (rawToken, tokenHash) = GenerateToken();
            var verificationToken = new EmailVerificationToken
            {
                Id         = Guid.NewGuid(),
                UserId     = created.Id,
                TokenHash  = tokenHash,
                ExpiresAt  = DateTime.UtcNow.AddHours(24),
            };
            await _userRepo.SaveEmailVerificationTokenAsync(verificationToken);

            // Send verification email — failure is logged but does not fail the request (Req 7.5)
            try
            {
                await _emailService.SendVerificationEmailAsync(created.Email, created.FullName, rawToken);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to send verification email to {Email}", created.Email);
            }

            return StatusCode(201, new
            {
                message = "Registration successful. Please check your email to verify your account.",
                userId  = created.Id,
            });
        }

        // ── POST /api/auth/verify-email ───────────────────────────────────────

        /// <summary>
        /// Consume an email verification token and mark the user as verified.
        /// </summary>
        [HttpPost("verify-email")]
        [AllowAnonymous]
        public async Task<IActionResult> VerifyEmail([FromBody] VerifyEmailRequestDto dto)
        {
            var tokenHash = HashToken(dto.Token);
            var record    = await _userRepo.GetEmailVerificationTokenAsync(tokenHash);

            if (record is null)
                return BadRequest(new { error = "invalid_token" });

            if (record.UsedAt is not null)
                return BadRequest(new { error = "token_already_used" });

            // Check expiry in DB to avoid C# DateTime timezone issues
            if (await _userRepo.IsTokenExpiredAsync(tokenHash))
                return BadRequest(new { error = "token_expired" });

            // Mark token used and set user as verified (Req 8.1)
            await _userRepo.MarkEmailVerificationTokenUsedAsync(tokenHash);

            var user = await _userRepo.GetByIdAsync(record.UserId);
            if (user is not null)
            {
                user.IsVerified       = true;
                user.EmailVerifiedAt  = DateTime.UtcNow;
                await _userRepo.UpdateAsync(user);
            }

            return Ok(new { message = "Email verified successfully." });
        }

        // ── POST /api/auth/resend-verification ────────────────────────────────

        /// <summary>
        /// Invalidate old verification tokens and issue a new one.
        /// </summary>
        [HttpPost("resend-verification")]
        [AllowAnonymous]
        public async Task<IActionResult> ResendVerification([FromBody] ResendVerificationRequestDto dto)
        {
            var user = await _userRepo.GetByEmailAsync(dto.Email.ToLowerInvariant());

            // Always return 200 to prevent email enumeration
            if (user is null || user.IsVerified)
                return Ok(new { message = "If your account exists and is unverified, a new email has been sent." });

            // Invalidate previous tokens (Req 8.5)
            await _userRepo.InvalidatePreviousVerificationTokensAsync(user.Id);

            var (rawToken, tokenHash) = GenerateToken();
            var token = new EmailVerificationToken
            {
                Id        = Guid.NewGuid(),
                UserId    = user.Id,
                TokenHash = tokenHash,
                ExpiresAt = DateTime.UtcNow.AddHours(24),
            };
            await _userRepo.SaveEmailVerificationTokenAsync(token);

            try
            {
                await _emailService.SendVerificationEmailAsync(user.Email, user.FullName, rawToken);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to resend verification email to {Email}", user.Email);
            }

            return Ok(new { message = "If your account exists and is unverified, a new email has been sent." });
        }

        // ── POST /api/auth/login ──────────────────────────────────────────────

        /// <summary>
        /// Authenticate with email+password. Returns access token, refresh token,
        /// expiry, and user profile. Same 401 for wrong password or unknown email
        /// to prevent user enumeration (Req 9.4, 9.5).
        /// Rate-limited to 5 req/min per IP via IpRateLimiting (Req 9.7).
        /// </summary>
        [HttpPost("login")]
        [AllowAnonymous]
        public async Task<IActionResult> Login([FromBody] LoginRequestDto dto)
        {
            if (!ModelState.IsValid)
                return BadRequest(ModelState);

            var user = await _userRepo.GetByEmailAsync(dto.Email.ToLowerInvariant());
            if (user is null || !BCrypt.Net.BCrypt.Verify(dto.Password, user.PasswordHash))
                return Unauthorized(new { error = "invalid_credentials" });

            // Record last login (Req 9.6)
            user.LastLoginAt = DateTime.UtcNow;
            await _userRepo.UpdateAsync(user);

            // Issue tokens
            var (accessToken, expiresAt) = GenerateAccessToken(user);
            var (rawRefresh, refreshHash) = GenerateToken();

            var refreshToken = new RefreshToken
            {
                Id         = Guid.NewGuid(),
                UserId     = user.Id,
                TokenHash  = refreshHash,
                ExpiresAt  = DateTime.UtcNow.AddDays(30),
                DeviceInfo = dto.DeviceInfo,
            };
            await _userRepo.SaveRefreshTokenAsync(refreshToken);

            return Ok(new AuthResponseDto(
                AccessToken:  accessToken,
                RefreshToken: rawRefresh,
                ExpiresAt:    expiresAt,
                User: MapToProfileDto(user)
            ));
        }

        // ── POST /api/auth/refresh ────────────────────────────────────────────

        /// <summary>
        /// Exchange a valid refresh token for a new access + refresh token pair.
        /// Old refresh token is immediately revoked (rotation, Req 10.1).
        /// </summary>
        [HttpPost("refresh")]
        [AllowAnonymous]
        public async Task<IActionResult> Refresh([FromBody] RefreshTokenRequestDto dto)
        {
            var tokenHash = HashToken(dto.RefreshToken);
            var record    = await _userRepo.GetRefreshTokenAsync(tokenHash);

            if (record is null || record.RevokedAt is not null)
                return Unauthorized(new { error = "invalid_token" });

            if (record.ExpiresAt < DateTime.UtcNow)
                return Unauthorized(new { error = "token_expired" });

            // Revoke old token immediately (Req 10.1)
            await _userRepo.RevokeRefreshTokenAsync(tokenHash);

            var user = await _userRepo.GetByIdAsync(record.UserId);
            if (user is null || !user.IsActive)
                return Unauthorized(new { error = "invalid_token" });

            var (accessToken, expiresAt) = GenerateAccessToken(user);
            var (rawRefresh, refreshHash) = GenerateToken();

            var newRefreshToken = new RefreshToken
            {
                Id         = Guid.NewGuid(),
                UserId     = user.Id,
                TokenHash  = refreshHash,
                ExpiresAt  = DateTime.UtcNow.AddDays(30),
                DeviceInfo = record.DeviceInfo,
            };
            await _userRepo.SaveRefreshTokenAsync(newRefreshToken);

            return Ok(new AuthResponseDto(
                AccessToken:  accessToken,
                RefreshToken: rawRefresh,
                ExpiresAt:    expiresAt,
                User: MapToProfileDto(user)
            ));
        }

        // ── POST /api/auth/logout ─────────────────────────────────────────────

        /// <summary>Revoke the provided refresh token (Req 10.4).</summary>
        [HttpPost("logout")]
        [Authorize]
        public async Task<IActionResult> Logout([FromBody] LogoutRequestDto dto)
        {
            var tokenHash = HashToken(dto.RefreshToken);
            await _userRepo.RevokeRefreshTokenAsync(tokenHash);
            return Ok(new { message = "Logged out successfully." });
        }

        // ── POST /api/auth/forgot-password ────────────────────────────────────

        /// <summary>
        /// Always returns 200 regardless of email existence to prevent enumeration (Req 11.1).
        /// For registered emails: generates SHA-256 hashed reset token with 1-hour expiry (Req 11.2).
        /// </summary>
        [HttpPost("forgot-password")]
        [AllowAnonymous]
        public async Task<IActionResult> ForgotPassword([FromBody] ForgotPasswordRequestDto dto)
        {
            var user = await _userRepo.GetByEmailAsync(dto.Email.ToLowerInvariant());
            if (user is not null)
            {
                await _userRepo.InvalidatePreviousPasswordResetTokensAsync(user.Id);

                var (rawToken, tokenHash) = GenerateToken(32);
                var resetToken = new PasswordResetToken
                {
                    Id        = Guid.NewGuid(),
                    UserId    = user.Id,
                    TokenHash = tokenHash,
                    ExpiresAt = DateTime.UtcNow.AddHours(1),
                };
                await _userRepo.SavePasswordResetTokenAsync(resetToken);

                try
                {
                    await _emailService.SendPasswordResetEmailAsync(user.Email, user.FullName, rawToken);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Failed to send password reset email to {Email}", user.Email);
                }
            }

            // Always 200 (Req 11.1, 18.4)
            return Ok(new { message = "If that email is registered, a reset link has been sent." });
        }

        // ── POST /api/auth/reset-password ─────────────────────────────────────

        /// <summary>
        /// Validate reset token, update password hash, revoke all refresh tokens (Req 11.3, 11.4).
        /// </summary>
        [HttpPost("reset-password")]
        [AllowAnonymous]
        public async Task<IActionResult> ResetPassword([FromBody] ResetPasswordRequestDto dto)
        {
            var tokenHash = HashToken(dto.Token);
            var record    = await _userRepo.GetPasswordResetTokenAsync(tokenHash);

            if (record is null || record.UsedAt is not null)
                return BadRequest(new { error = "token_invalid" });

            if (await _userRepo.IsPasswordResetTokenExpiredAsync(tokenHash))
                return BadRequest(new { error = "token_invalid" });

            var user = await _userRepo.GetByIdAsync(record.UserId);
            if (user is null)
                return BadRequest(new { error = "token_invalid" });

            // Update password (Req 11.3)
            user.PasswordHash = BCrypt.Net.BCrypt.HashPassword(dto.NewPassword, workFactor: 12);
            await _userRepo.UpdateAsync(user);

            // Mark token used
            await _userRepo.MarkPasswordResetTokenUsedAsync(tokenHash);

            // Revoke all refresh tokens — force re-login on all devices (Req 11.4, 18.7)
            await _userRepo.RevokeAllRefreshTokensForUserAsync(user.Id);

            return Ok(new { message = "Password reset successfully." });
        }

        // ── Helpers ───────────────────────────────────────────────────────────
        /// <summary>
        /// Generate a cryptographically random token and return (rawToken, sha256Hash).
        /// Raw token is sent in email; only the hash is stored in DB (Req 8.6).
        /// </summary>
        private static (string raw, string hash) GenerateToken(int byteLength = 32)
        {
            var bytes = RandomNumberGenerator.GetBytes(byteLength);
            var raw   = Convert.ToBase64String(bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_');
            var hash  = HashToken(raw);
            return (raw, hash);
        }

        /// <summary>Returns the SHA-256 hex digest of a raw token string.</summary>
        internal static string HashToken(string rawToken)
        {
            var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(rawToken));
            return Convert.ToHexString(bytes).ToLowerInvariant();
        }

        /// <summary>
        /// Issue a signed HS256 JWT with 15-minute expiry.
        /// Claims: sub, email, role, name (Req 9.2).
        /// </summary>
        private (string token, DateTime expiresAt) GenerateAccessToken(User user)
        {
            var secret  = _config["AppSettings:JwtSecret"]
                          ?? throw new InvalidOperationException("JwtSecret not configured");
            var key     = new SymmetricSecurityKey(Encoding.ASCII.GetBytes(secret));
            var creds   = new SigningCredentials(key, SecurityAlgorithms.HmacSha256);
            var expires = DateTime.UtcNow.AddMinutes(15);

            var claims = new[]
            {
                new Claim(JwtRegisteredClaimNames.Sub,   user.Id.ToString()),
                new Claim(JwtRegisteredClaimNames.Email, user.Email),
                new Claim("role",                        user.Role),
                new Claim("name",                        user.FullName),
                new Claim(JwtRegisteredClaimNames.Jti,   Guid.NewGuid().ToString()),
            };

            var token = new JwtSecurityToken(
                claims:            claims,
                expires:           expires,
                signingCredentials: creds);

            return (new JwtSecurityTokenHandler().WriteToken(token), expires);
        }

        private static UserProfileDto MapToProfileDto(User user) =>
            new(user.Id, user.FullName, user.Email, user.Mobile,
                user.AvatarUrl, user.IsVerified, user.CreatedAt, user.Role ?? "user");
    }
}