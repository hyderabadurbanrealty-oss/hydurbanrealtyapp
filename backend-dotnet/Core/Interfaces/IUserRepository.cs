using HyderabadUrbanReality.Core.Entities;

namespace HyderabadUrbanReality.Core.Interfaces
{
    /// <summary>
    /// Data access contract for user accounts and authentication tokens.
    /// </summary>
    public interface IUserRepository
    {
        // ── User CRUD ─────────────────────────────────────────────────────────
        Task<User?> GetByEmailAsync(string email);
        Task<User?> GetByIdAsync(Guid id);
        Task<User> CreateAsync(User user);
        Task UpdateAsync(User user);
        Task<bool> EmailExistsAsync(string email);

        // ── Refresh tokens ────────────────────────────────────────────────────
        Task<RefreshToken?> GetRefreshTokenAsync(string tokenHash);
        Task SaveRefreshTokenAsync(RefreshToken token);
        Task RevokeRefreshTokenAsync(string tokenHash);
        Task RevokeAllRefreshTokensForUserAsync(Guid userId);

        // ── Password reset tokens ─────────────────────────────────────────────
        Task<PasswordResetToken?> GetPasswordResetTokenAsync(string tokenHash);
        Task SavePasswordResetTokenAsync(PasswordResetToken token);
        Task MarkPasswordResetTokenUsedAsync(string tokenHash);
        Task InvalidatePreviousPasswordResetTokensAsync(Guid userId);

        // ── Email verification tokens ─────────────────────────────────────────
        Task<EmailVerificationToken?> GetEmailVerificationTokenAsync(string tokenHash);
        Task SaveEmailVerificationTokenAsync(EmailVerificationToken token);
        Task MarkEmailVerificationTokenUsedAsync(string tokenHash);
        Task InvalidatePreviousVerificationTokensAsync(Guid userId);
        Task<bool> IsTokenExpiredAsync(string tokenHash);
        Task<bool> IsPasswordResetTokenExpiredAsync(string tokenHash);

        // ── Admin user management ─────────────────────────────────────────────
        Task<IEnumerable<User>> GetAllUsersAsync(int page = 1, int pageSize = 50);
        Task<int> GetUserCountAsync();
        Task DeleteUserAsync(Guid userId);
        Task UpdateUserRoleAsync(Guid userId, string role);
        Task UpdateUserStatusAsync(Guid userId, bool isActive);
    }
}
