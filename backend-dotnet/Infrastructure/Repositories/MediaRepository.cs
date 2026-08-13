using Dapper;
using Npgsql;

namespace HyderabadUrbanReality.Infrastructure.Repositories
{
    public class MediaRepository
    {
        private readonly string _connectionString;

        public MediaRepository(IConfiguration configuration)
        {
            _connectionString = configuration.GetConnectionString("DefaultConnection")!;
        }

        public async Task<IEnumerable<dynamic>> GetByProjectAsync(string projectId, string? mediaType = null)
        {
            var sql = mediaType != null
                ? "SELECT * FROM project_media WHERE project_id=@projectId AND media_type=@mediaType ORDER BY sort_order, created_at"
                : "SELECT * FROM project_media WHERE project_id=@projectId ORDER BY media_type, sort_order, created_at";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.QueryAsync<dynamic>(sql, new { projectId, mediaType });
        }

        public async Task<dynamic?> GetByIdAsync(Guid id)
        {
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.QuerySingleOrDefaultAsync<dynamic>(
                "SELECT * FROM project_media WHERE id=@id", new { id });
        }

        public async Task<Guid> AddAsync(string projectId, string mediaType, string title,
            string fileUrl, string? fileName, long? fileSize, string? mimeType, int sortOrder = 0)
        {
            const string sql = @"
                INSERT INTO project_media
                    (id, project_id, media_type, title, file_url, file_name, file_size, mime_type, sort_order)
                VALUES
                    (gen_random_uuid(), @projectId, @mediaType, @title, @fileUrl, @fileName, @fileSize, @mimeType, @sortOrder)
                RETURNING id";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.ExecuteScalarAsync<Guid>(sql,
                new { projectId, mediaType, title, fileUrl, fileName, fileSize, mimeType, sortOrder });
        }

        public async Task<bool> UpdateAsync(Guid id, string title, int sortOrder)
        {
            const string sql = "UPDATE project_media SET title=@title, sort_order=@sortOrder, updated_at=NOW() WHERE id=@id";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.ExecuteAsync(sql, new { id, title, sortOrder }) > 0;
        }

        public async Task<string?> DeleteAsync(Guid id)
        {
            const string sql = "DELETE FROM project_media WHERE id=@id RETURNING file_name";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.ExecuteScalarAsync<string>(sql, new { id });
        }

        public async Task<bool> DeleteAllByProjectAsync(string projectId)
        {
            const string sql = "DELETE FROM project_media WHERE project_id=@projectId";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.ExecuteAsync(sql, new { projectId }) > 0;
        }
    }
}
