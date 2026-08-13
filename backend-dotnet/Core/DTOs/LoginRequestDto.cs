using System.ComponentModel.DataAnnotations;

namespace HyderabadUrbanReality.Core.DTOs
{
    public class LoginRequestDto
    {
        [Required]
        [EmailAddress]
        public string Email { get; set; } = string.Empty;

        [Required]
        public string Password { get; set; } = string.Empty;

        public string? DeviceInfo { get; set; }

        // Backward-compatibility alias for existing admin login (ProjectController)
        public string Username => Email;
    }
}
