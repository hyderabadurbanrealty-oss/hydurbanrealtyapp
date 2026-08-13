using Dapper;
using HyderabadUrbanReality.Core.Entities;
using HyderabadUrbanReality.Core.Interfaces;
using Npgsql;
using System.Text.Json;

namespace HyderabadUrbanReality.Infrastructure.Repositories
{
    /// <summary>
    /// PostgreSQL implementation of IUserDataRepository using Dapper.
    /// Covers saved properties, favorites, saved searches, and comparison results.
    /// All SQL uses parameterized queries (Req 18.5).
    /// IInputSanitizer is applied to all user-provided string values before they reach this layer (Req 18.6).
    /// </summary>
    public class UserDataRepository : IUserDataRepository
    {
        private readonly string _connectionString;
        private readonly ILogger<UserDataRepository> _logger;

        public UserDataRepository(IConfiguration configuration, ILogger<UserDataRepository> logger)
        {
            _connectionString = configuration.GetConnectionString("DefaultConnection")
                ?? throw new InvalidOperationException("ConnectionStrings:DefaultConnection is not configured.");
            _logger = logger;
        }

        // ── Saved Properties ──────────────────────────────────────────────────

        public async Task<IEnumerable<SavedProperty>> GetSavedPropertiesAsync(Guid userId)
        {
            const string sql = @"
                SELECT sp.id, sp.user_id, sp.project_id, sp.notes, sp.created_at,
                       p.project_name, p.locality, p.district, p.project_status
                FROM   saved_properties sp
                LEFT JOIN projects p ON p.id = sp.project_id
                WHERE  sp.user_id = @userId
                ORDER  BY sp.created_at DESC";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.QueryAsync<SavedProperty>(sql, new { userId });
        }

        public async Task<SavedProperty?> GetSavedPropertyAsync(Guid userId, string projectId)
        {
            const string sql = @"
                SELECT * FROM saved_properties
                WHERE user_id = @userId AND project_id = @projectId
                LIMIT 1";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.QuerySingleOrDefaultAsync<SavedProperty>(sql, new { userId, projectId });
        }

        public async Task<SavedProperty> AddSavedPropertyAsync(SavedProperty item)
        {
            const string sql = @"
                INSERT INTO saved_properties (id, user_id, project_id, notes, created_at)
                VALUES (@Id, @UserId, @ProjectId, @Notes, NOW())
                RETURNING *";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.QuerySingleAsync<SavedProperty>(sql, item);
        }

        public async Task RemoveSavedPropertyAsync(Guid userId, string projectId)
        {
            const string sql = "DELETE FROM saved_properties WHERE user_id = @userId AND project_id = @projectId";
            await using var conn = new NpgsqlConnection(_connectionString);
            await conn.ExecuteAsync(sql, new { userId, projectId });
        }

        // ── Favorites ─────────────────────────────────────────────────────────

        public async Task<IEnumerable<Favorite>> GetFavoritesAsync(Guid userId)
        {
            const string sql = @"
                SELECT * FROM favorites
                WHERE  user_id = @userId
                ORDER  BY created_at DESC";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.QueryAsync<Favorite>(sql, new { userId });
        }

        public async Task<bool> IsFavoritedAsync(Guid userId, string projectId)
        {
            const string sql = "SELECT COUNT(1) FROM favorites WHERE user_id = @userId AND project_id = @projectId";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.ExecuteScalarAsync<int>(sql, new { userId, projectId }) > 0;
        }

        public async Task AddFavoriteAsync(Guid userId, string projectId)
        {
            const string sql = @"
                INSERT INTO favorites (id, user_id, project_id, created_at)
                VALUES (gen_random_uuid(), @userId, @projectId, NOW())
                ON CONFLICT (user_id, project_id) DO NOTHING";
            await using var conn = new NpgsqlConnection(_connectionString);
            await conn.ExecuteAsync(sql, new { userId, projectId });
        }

        public async Task RemoveFavoriteAsync(Guid userId, string projectId)
        {
            const string sql = "DELETE FROM favorites WHERE user_id = @userId AND project_id = @projectId";
            await using var conn = new NpgsqlConnection(_connectionString);
            await conn.ExecuteAsync(sql, new { userId, projectId });
        }

        // ── Saved Searches ────────────────────────────────────────────────────

        public async Task<IEnumerable<SavedSearch>> GetSavedSearchesAsync(Guid userId)
        {
            const string sql = @"
                SELECT * FROM saved_searches
                WHERE  user_id = @userId
                ORDER  BY created_at DESC";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.QueryAsync<SavedSearch>(sql, new { userId });
        }

        public async Task<SavedSearch?> GetSavedSearchAsync(Guid userId, Guid searchId)
        {
            const string sql = "SELECT * FROM saved_searches WHERE user_id = @userId AND id = @searchId LIMIT 1";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.QuerySingleOrDefaultAsync<SavedSearch>(sql, new { userId, searchId });
        }

        public async Task<SavedSearch> AddSavedSearchAsync(SavedSearch search)
        {
            const string sql = @"
                INSERT INTO saved_searches (id, user_id, name, filters, created_at, updated_at)
                VALUES (@Id, @UserId, @Name, @Filters::jsonb, NOW(), NOW())
                RETURNING *";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.QuerySingleAsync<SavedSearch>(sql, search);
        }

        public async Task<SavedSearch?> UpdateSavedSearchAsync(Guid userId, Guid searchId, string? name, JsonDocument? filters)
        {
            const string sql = @"
                UPDATE saved_searches
                SET name       = COALESCE(@name, name),
                    filters    = COALESCE(@filters::jsonb, filters),
                    updated_at = NOW()
                WHERE id = @searchId AND user_id = @userId
                RETURNING *";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.QuerySingleOrDefaultAsync<SavedSearch>(sql, new
            {
                name,
                filters = filters is not null ? filters.RootElement.GetRawText() : null,
                searchId,
                userId
            });
        }

        public async Task DeleteSavedSearchAsync(Guid userId, Guid searchId)
        {
            const string sql = "DELETE FROM saved_searches WHERE user_id = @userId AND id = @searchId";
            await using var conn = new NpgsqlConnection(_connectionString);
            await conn.ExecuteAsync(sql, new { userId, searchId });
        }

        public async Task UpdateSavedSearchRunStatsAsync(Guid searchId, int resultCount)
        {
            const string sql = @"
                UPDATE saved_searches
                SET last_run_at  = NOW(),
                    result_count = @resultCount
                WHERE id = @searchId";
            await using var conn = new NpgsqlConnection(_connectionString);
            await conn.ExecuteAsync(sql, new { searchId, resultCount });
        }

        // ── Comparison Results ────────────────────────────────────────────────

        public async Task<IEnumerable<ComparisonResult>> GetComparisonsAsync(Guid userId)
        {
            const string sql = @"
                SELECT * FROM comparison_results
                WHERE  user_id = @userId
                ORDER  BY created_at DESC";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.QueryAsync<ComparisonResult>(sql, new { userId });
        }

        public async Task<ComparisonResult?> GetComparisonAsync(Guid userId, Guid comparisonId)
        {
            const string sql = @"
                SELECT * FROM comparison_results
                WHERE user_id = @userId AND id = @comparisonId
                LIMIT 1";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.QuerySingleOrDefaultAsync<ComparisonResult>(sql, new { userId, comparisonId });
        }

        public async Task<ComparisonResult> AddComparisonAsync(ComparisonResult comparison)
        {
            const string sql = @"
                INSERT INTO comparison_results (id, user_id, name, project_ids, snapshot, created_at, updated_at)
                VALUES (@Id, @UserId, @Name, @ProjectIds, @Snapshot::jsonb, NOW(), NOW())
                RETURNING *";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.QuerySingleAsync<ComparisonResult>(sql, comparison);
        }

        public async Task DeleteComparisonAsync(Guid userId, Guid comparisonId)
        {
            const string sql = "DELETE FROM comparison_results WHERE user_id = @userId AND id = @comparisonId";
            await using var conn = new NpgsqlConnection(_connectionString);
            await conn.ExecuteAsync(sql, new { userId, comparisonId });
        }
    }
}
