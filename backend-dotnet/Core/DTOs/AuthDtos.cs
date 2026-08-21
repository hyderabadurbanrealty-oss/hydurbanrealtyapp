namespace HyderabadUrbanReality.Core.DTOs
{
    // Request DTOs
    public record RegisterRequestDto(string FullName, string Email, string Password, string? Mobile);
    public record RefreshTokenRequestDto(string RefreshToken);
    public record LogoutRequestDto(string RefreshToken);
    public record ForgotPasswordRequestDto(string Email);
    public record ResetPasswordRequestDto(string Token, string NewPassword);
    public record VerifyEmailRequestDto(string Token);
    public record ResendVerificationRequestDto(string Email);
    public record ChangePasswordRequestDto(string CurrentPassword, string NewPassword);
    public record UpdateProfileRequestDto(string? FullName, string? Mobile, string? AvatarUrl);
    public record GoogleLoginRequestDto(string IdToken);    // Google credential token from client SDK

    // Response DTOs
    public record UserProfileDto(
        Guid Id,
        string FullName,
        string Email,
        string? Mobile,
        string? AvatarUrl,
        bool IsVerified,
        DateTime CreatedAt,
        string Role = "user");

    public record AuthResponseDto(
        string AccessToken,
        string RefreshToken,
        DateTime ExpiresAt,
        UserProfileDto User);
}
