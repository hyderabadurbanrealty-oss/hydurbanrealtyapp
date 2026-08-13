using Dapper;
using Npgsql;

namespace HyderabadUrbanReality.Infrastructure.Repositories
{
    public class Review
    {
        public int Id { get; set; }
        public string ProjectId { get; set; } = string.Empty;
        public string Name { get; set; } = string.Empty;
        public string Email { get; set; } = string.Empty;
        public string Contact { get; set; } = string.Empty;
        public int Rating { get; set; }
        public string ReviewText { get; set; } = string.Empty;
        public bool IsApproved { get; set; }
        public DateTime CreatedAt { get; set; }
    }

    public class ReviewRepository
    {
        private readonly string _connectionString;

        public ReviewRepository(IConfiguration configuration)
        {
            _connectionString = configuration.GetConnectionString("DefaultConnection")
                ?? throw new InvalidOperationException("ConnectionStrings:DefaultConnection is not configured.");
        }

        public async Task<int> InsertAsync(Review review)
        {
            const string sql = @"
                INSERT INTO reviews (project_id, name, email, contact, rating, review, is_approved, created_at)
                VALUES (@ProjectId, @Name, @Email, @Contact, @Rating, @ReviewText, FALSE, NOW())
                RETURNING id";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.ExecuteScalarAsync<int>(sql, review);
        }

        public async Task<IEnumerable<Review>> GetApprovedByProjectAsync(string projectId)
        {
            const string sql = @"
                SELECT id, project_id, name, email, contact, rating,
                       review AS review_text, is_approved, created_at
                FROM reviews
                WHERE project_id = @projectId AND is_approved = TRUE
                ORDER BY created_at DESC";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.QueryAsync<Review>(sql, new { projectId });
        }

        public async Task<IEnumerable<Review>> GetAllByProjectAsync(string projectId)
        {
            const string sql = @"
                SELECT id, project_id, name, email, contact, rating,
                       review AS review_text, is_approved, created_at
                FROM reviews
                WHERE project_id = @projectId
                ORDER BY created_at DESC";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.QueryAsync<Review>(sql, new { projectId });
        }

        public async Task<IEnumerable<Review>> GetAllAsync(int page = 1, int pageSize = 50)
        {
            const string sql = @"
                SELECT id, project_id, name, email, contact, rating,
                       review AS review_text, is_approved, created_at
                FROM reviews
                ORDER BY created_at DESC
                LIMIT @pageSize OFFSET @offset";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.QueryAsync<Review>(sql, new { pageSize, offset = (page - 1) * pageSize });
        }

        public async Task<bool> ApproveAsync(int id)
        {
            const string sql = "UPDATE reviews SET is_approved = TRUE WHERE id = @id";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.ExecuteAsync(sql, new { id }) > 0;
        }

        public async Task<bool> DeleteAsync(int id)
        {
            const string sql = "DELETE FROM reviews WHERE id = @id";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.ExecuteAsync(sql, new { id }) > 0;
        }
    }
}
