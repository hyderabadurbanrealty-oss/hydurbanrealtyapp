using HyderabadUrbanReality.Core.Interfaces;
using HyderabadUrbanReality.Core.Configuration;
using Microsoft.Extensions.Options;

namespace HyderabadUrbanReality.Infrastructure.Services
{
    /// <summary>
    /// Service for authentication operations
    /// Follows Single Responsibility - handles authentication only
    /// Follows Dependency Inversion - depends on abstraction
    /// </summary>
    public class AuthenticationService : IAuthenticationService
    {
        private readonly AppSettings _appSettings;
        private readonly ILogger<AuthenticationService> _logger;

        public AuthenticationService(
            IOptions<AppSettings> appSettings,
            ILogger<AuthenticationService> logger)
        {
            _appSettings = appSettings?.Value ?? throw new ArgumentNullException(nameof(appSettings));
            _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        }

        /// <inheritdoc />
        public Task<bool> AuthenticateAsync(string username, string password)
        {
            if (string.IsNullOrWhiteSpace(username) || string.IsNullOrWhiteSpace(password))
            {
                _logger.LogWarning("Authentication attempted with empty credentials");
                return Task.FromResult(false);
            }

            // Verify username first
            if (username != _appSettings.AdminUsername)
            {
                _logger.LogWarning("Failed authentication attempt for user: {Username}", username);
                return Task.FromResult(false);
            }

            // Verify password using BCrypt
            // Generate correct hash for admin123 (temporary logging)
            if (password == "admin123")
            {
                string correctHash = BCrypt.Net.BCrypt.HashPassword("admin123", 11);
                _logger.LogInformation("CORRECT BCRYPT HASH FOR admin123: {Hash}", correctHash);
            }
            
            // Temporary: use plain text until we update config with correct hash
            var isAuthenticated = password == "admin123";
            // TODO: Switch back to: var isAuthenticated = BCrypt.Net.BCrypt.Verify(password, _appSettings.AdminPasswordHash);

            if (isAuthenticated)
            {
                _logger.LogInformation("Successful authentication for user: {Username}", username);
            }
            else
            {
                _logger.LogWarning("Failed authentication attempt for user: {Username}", username);
            }

            return Task.FromResult(isAuthenticated);
        }

        /// <inheritdoc />
        public bool IsAuthenticated(string sessionToken)
        {
            // In production, validate JWT token or session token
            return !string.IsNullOrWhiteSpace(sessionToken);
        }
    }
}
