using Dapper;
using Npgsql;

namespace HyderabadUrbanReality.Infrastructure.Repositories
{
    public class ScheduleVisit
    {
        public int Id { get; set; }
        public string? ProjectId { get; set; }
        public string? ProjectName { get; set; }
        public string Name { get; set; } = string.Empty;
        public string Email { get; set; } = string.Empty;
        public string Mobile { get; set; } = string.Empty;
        public DateOnly VisitDate { get; set; }
        public string VisitTime { get; set; } = string.Empty;
        public string? Message { get; set; }
        public string? LocationAddress { get; set; }
        public double? LocationLat { get; set; }
        public double? LocationLng { get; set; }
        public string? LocationMapUrl { get; set; }
        public string Status { get; set; } = "pending";
        public DateTime CreatedAt { get; set; }
    }

    public class ScheduleVisitRepository
    {
        private readonly string _connectionString;

        public ScheduleVisitRepository(IConfiguration configuration)
        {
            _connectionString = configuration.GetConnectionString("DefaultConnection")
                ?? throw new InvalidOperationException("ConnectionStrings:DefaultConnection is not configured.");
        }

        public async Task<int> InsertAsync(ScheduleVisit visit)
        {
            const string sql = @"
                INSERT INTO schedule_visits
                    (project_id, project_name, name, email, mobile, visit_date, visit_time,
                     message, location_address, location_lat, location_lng, location_map_url,
                     status, created_at)
                VALUES
                    (@ProjectId, @ProjectName, @Name, @Email, @Mobile, @VisitDate, @VisitTime,
                     @Message, @LocationAddress, @LocationLat, @LocationLng, @LocationMapUrl,
                     'pending', NOW())
                RETURNING id";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.ExecuteScalarAsync<int>(sql, visit);
        }

        public async Task<IEnumerable<ScheduleVisit>> GetAllAsync(int page = 1, int pageSize = 50)
        {
            const string sql = @"
                SELECT id, project_id, project_name, name, email, mobile,
                       visit_date, visit_time, message,
                       location_address, location_lat, location_lng, location_map_url,
                       status, created_at
                FROM schedule_visits
                ORDER BY created_at DESC
                LIMIT @pageSize OFFSET @offset";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.QueryAsync<ScheduleVisit>(sql, new { pageSize, offset = (page - 1) * pageSize });
        }

        public async Task<bool> UpdateStatusAsync(int id, string status)
        {
            const string sql = "UPDATE schedule_visits SET status = @status WHERE id = @id";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.ExecuteAsync(sql, new { id, status }) > 0;
        }

        public async Task<bool> DeleteAsync(int id)
        {
            const string sql = "DELETE FROM schedule_visits WHERE id = @id";
            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.ExecuteAsync(sql, new { id }) > 0;
        }
    }
}
