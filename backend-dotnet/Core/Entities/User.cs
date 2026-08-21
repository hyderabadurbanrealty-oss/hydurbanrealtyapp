namespace HyderabadUrbanReality.Core.Entities
{
    public class User
    {
        public Guid Id { get; set; }
        public string Email { get; set; } = string.Empty;
        public string? PasswordHash { get; set; }    // nullable — Google-only users have no password
        public string FullName { get; set; } = string.Empty;
        public string? Mobile { get; set; }
        public string? AvatarUrl { get; set; }
        public string? GoogleId { get; set; }        // Google subject ID for OAuth lookup
        public bool IsVerified { get; set; } = false;
        public bool IsActive { get; set; } = true;
        public string Role { get; set; } = "user";
        public DateTime? EmailVerifiedAt { get; set; }
        public DateTime? LastLoginAt { get; set; }
        public DateTime CreatedAt { get; set; }
        public DateTime UpdatedAt { get; set; }
    }
}
