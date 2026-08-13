using Dapper;
using HyderabadUrbanReality.Core.Entities;
using HyderabadUrbanReality.Core.Interfaces;
using Npgsql;

namespace HyderabadUrbanReality.Infrastructure.Repositories
{
    /// <summary>
    /// PostgreSQL implementation of IUserRepository using Dapper.
    /// All SQL uses parameterized queries to prevent injection.
    /// </summary>
    public class UserRepository : IUserRepository
    {
        private readonly string _connectionString;
        private readonly ILogger<UserRepository> _logger;

        public UserRepository(IConfiguration configuration, ILogger<UserRepository> logger)
        {
            _connectionString = configuration.GetConnectionString("DefaultConnection")
                ?? throw new InvalidOperationException("ConnectionStrings:DefaultConnection is not configured.");
            _logger = logger;
        }

        // ── User CRUD ─────────────────────────────────────────────────────────

        public async Task<User?> GetByEmailAsync(string email)
        {
            const string sql = "SELECT * FROM users WHERE email = @email LIMIT 1";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.QuerySingleOrDefaultAsync<User>(sql, new { email });
        }

        public async Task<User?> GetByIdAsync(Guid id)
        {
            const string sql = "SELECT * FROM users WHERE id = @id LIMIT 1";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.QuerySingleOrDefaultAsync<User>(sql, new { id });
        }

        public async Task<User> CreateAsync(User user)
        {
            const string sql = @"
                INSERT INTO users
                    (id, email, password_hash, full_name, mobile, avatar_url,
                     is_verified, is_active, role, created_at, updated_at)
                VALUES
                    (@Id, @Email, @PasswordHash, @FullName, @Mobile, @AvatarUrl,
                     @IsVerified, @IsActive, @Role, NOW(), NOW())
                RETURNING *";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.QuerySingleAsync<User>(sql, user);
        }

        public async Task UpdateAsync(User user)
        {
            const string sql = @"
                UPDATE users
                SET full_name        = @FullName,
                    mobile           = @Mobile,
                    avatar_url       = @AvatarUrl,
                    password_hash    = @PasswordHash,
                    is_verified      = @IsVerified,
                    is_active        = @IsActive,
                    email_verified_at= @EmailVerifiedAt,
                    last_login_at    = @LastLoginAt,
                    updated_at       = NOW()
                WHERE id = @Id";
            await using var conn = new NpgsqlConnection(_connectionString);
            await conn.ExecuteAsync(sql, user);
        }

        public async Task<bool> EmailExistsAsync(string email)
        {
            const string sql = "SELECT COUNT(1) FROM users WHERE email = @email";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.ExecuteScalarAsync<int>(sql, new { email }) > 0;
        }

        // ── Refresh tokens ────────────────────────────────────────────────────

        public async Task<RefreshToken?> GetRefreshTokenAsync(string tokenHash)
        {
            const string sql = "SELECT * FROM refresh_tokens WHERE token_hash = @tokenHash LIMIT 1";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.QuerySingleOrDefaultAsync<RefreshToken>(sql, new { tokenHash });
        }

        public async Task SaveRefreshTokenAsync(RefreshToken token)
        {
            const string sql = @"
                INSERT INTO refresh_tokens (id, user_id, token_hash, expires_at, device_info, created_at)
                VALUES (@Id, @UserId, @TokenHash, @ExpiresAt, @DeviceInfo, NOW())";
            await using var conn = new NpgsqlConnection(_connectionString);
            await conn.ExecuteAsync(sql, token);
        }

        public async Task RevokeRefreshTokenAsync(string tokenHash)
        {
            const string sql = "UPDATE refresh_tokens SET revoked_at = NOW() WHERE token_hash = @tokenHash";
            await using var conn = new NpgsqlConnection(_connectionString);
            await conn.ExecuteAsync(sql, new { tokenHash });
        }

        public async Task RevokeAllRefreshTokensForUserAsync(Guid userId)
        {
            const string sql = @"
                UPDATE refresh_tokens
                SET revoked_at = NOW()
                WHERE user_id = @userId AND revoked_at IS NULL";
            await using var conn = new NpgsqlConnection(_connectionString);
            await conn.ExecuteAsync(sql, new { userId });
        }

        // ── Password reset tokens ─────────────────────────────────────────────

        public async Task<PasswordResetToken?> GetPasswordResetTokenAsync(string tokenHash)
        {
            // Always match on the specific hash — token is already unique
            const string sql = "SELECT * FROM password_reset_tokens WHERE token_hash = @tokenHash ORDER BY created_at DESC LIMIT 1";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.QuerySingleOrDefaultAsync<PasswordResetToken>(sql, new { tokenHash });
        }

        public async Task SavePasswordResetTokenAsync(PasswordResetToken token)
        {
            const string sql = @"
                INSERT INTO password_reset_tokens (id, user_id, token_hash, expires_at, created_at)
                VALUES (@Id, @UserId, @TokenHash, NOW() + INTERVAL '1 hour', NOW())";
            await using var conn = new NpgsqlConnection(_connectionString);
            await conn.ExecuteAsync(sql, token);
        }

        public async Task InvalidatePreviousPasswordResetTokensAsync(Guid userId)
        {
            // Mark all unused, unexpired tokens for this user as used so only
            // the most recently issued token is valid (prevents token accumulation).
            const string sql = @"
                UPDATE password_reset_tokens
                SET used_at = NOW()
                WHERE user_id = @userId
                  AND used_at IS NULL
                  AND expires_at > NOW()";
            await using var conn = new NpgsqlConnection(_connectionString);
            await conn.ExecuteAsync(sql, new { userId });
        }

        public async Task MarkPasswordResetTokenUsedAsync(string tokenHash)
        {
            const string sql = "UPDATE password_reset_tokens SET used_at = NOW() WHERE token_hash = @tokenHash";
            await using var conn = new NpgsqlConnection(_connectionString);
            await conn.ExecuteAsync(sql, new { tokenHash });
        }

        // ── Email verification tokens ─────────────────────────────────────────

        public async Task<EmailVerificationToken?> GetEmailVerificationTokenAsync(string tokenHash)
        {
            // Check expiry in SQL so we avoid C# DateTime timezone conversion issues
            const string sql = @"
                SELECT *, (expires_at > NOW()) AS is_valid
                FROM email_verification_tokens 
                WHERE token_hash = @tokenHash LIMIT 1";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.QuerySingleOrDefaultAsync<EmailVerificationToken>(sql, new { tokenHash });
        }

        public async Task<bool> IsTokenExpiredAsync(string tokenHash)
        {
            const string sql = "SELECT expires_at <= NOW() FROM email_verification_tokens WHERE token_hash = @tokenHash LIMIT 1";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.ExecuteScalarAsync<bool>(sql, new { tokenHash });
        }

        public async Task<bool> IsPasswordResetTokenExpiredAsync(string tokenHash)
        {
            const string sql = "SELECT expires_at <= NOW() FROM password_reset_tokens WHERE token_hash = @tokenHash LIMIT 1";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.ExecuteScalarAsync<bool>(sql, new { tokenHash });
        }

        public async Task SaveEmailVerificationTokenAsync(EmailVerificationToken token)
        {
            const string sql = @"
                INSERT INTO email_verification_tokens (id, user_id, token_hash, expires_at, created_at)
                VALUES (@Id, @UserId, @TokenHash, NOW() + INTERVAL '24 hours', NOW())";
            await using var conn = new NpgsqlConnection(_connectionString);
            await conn.ExecuteAsync(sql, token);
        }

        public async Task MarkEmailVerificationTokenUsedAsync(string tokenHash)
        {
            const string sql = "UPDATE email_verification_tokens SET used_at = NOW() WHERE token_hash = @tokenHash";
            await using var conn = new NpgsqlConnection(_connectionString);
            await conn.ExecuteAsync(sql, new { tokenHash });
        }

        public async Task InvalidatePreviousVerificationTokensAsync(Guid userId)
        {
            const string sql = @"
                UPDATE email_verification_tokens
                SET used_at = NOW()
                WHERE user_id = @userId AND used_at IS NULL";
            await using var conn = new NpgsqlConnection(_connectionString);
            await conn.ExecuteAsync(sql, new { userId });
        }

        // ── Admin user management ─────────────────────────────────────────────

        public async Task<IEnumerable<User>> GetAllUsersAsync(int page = 1, int pageSize = 50)
        {
            const string sql = @"
                SELECT * FROM users
                ORDER BY created_at DESC
                LIMIT @pageSize OFFSET @offset";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.QueryAsync<User>(sql, new { pageSize, offset = (page - 1) * pageSize });
        }

        public async Task<int> GetUserCountAsync()
        {
            const string sql = "SELECT COUNT(*) FROM users";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.ExecuteScalarAsync<int>(sql);
        }

        public async Task DeleteUserAsync(Guid userId)
        {
            const string sql = "DELETE FROM users WHERE id = @userId";
            await using var conn = new NpgsqlConnection(_connectionString);
            await conn.ExecuteAsync(sql, new { userId });
        }

        public async Task UpdateUserRoleAsync(Guid userId, string role)
        {
            const string sql = "UPDATE users SET role = @role, updated_at = NOW() WHERE id = @userId";
            await using var conn = new NpgsqlConnection(_connectionString);
            await conn.ExecuteAsync(sql, new { userId, role });
        }

        public async Task UpdateUserStatusAsync(Guid userId, bool isActive)
        {
            const string sql = "UPDATE users SET is_active = @isActive, updated_at = NOW() WHERE id = @userId";
            await using var conn = new NpgsqlConnection(_connectionString);
            await conn.ExecuteAsync(sql, new { userId, isActive });
        }
    }
}
