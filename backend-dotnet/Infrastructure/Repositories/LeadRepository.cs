using Dapper;
using HyderabadUrbanReality.Models;
using Npgsql;

namespace HyderabadUrbanReality.Infrastructure.Repositories
{
    /// <summary>
    /// Saves and retrieves leads (enquiries) from the PostgreSQL leads table.
    /// </summary>
    public class LeadRepository
    {
        private readonly string _connectionString;

        public LeadRepository(IConfiguration configuration)
        {
            _connectionString = configuration.GetConnectionString("DefaultConnection")
                ?? throw new InvalidOperationException("ConnectionStrings:DefaultConnection is not configured.");
        }

        public async Task<int> InsertAsync(Lead lead)
        {
            const string sql = @"
                INSERT INTO leads (name, email, mobile, area_of_interest,
                                   project_name, project_id, device_fingerprint, source, created_at)
                VALUES (@Name, @Email, @Mobile, @AreaOfInterest,
                        @ProjectName, @ProjectId, @DeviceFingerprint, @Source, NOW())
                RETURNING id";

            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.ExecuteScalarAsync<int>(sql, new
            {
                lead.Name,
                lead.Email,
                lead.Mobile,
                lead.AreaOfInterest,
                lead.ProjectName,
                lead.ProjectId,
                lead.DeviceFingerprint,
                Source = lead.Source ?? "property_detail_page"
            });
        }

        public async Task<IEnumerable<dynamic>> GetAllAsync()
        {
            const string sql = @"
                SELECT id, name, email, mobile, area_of_interest AS ""areaOfInterest"",
                       project_name AS ""projectName"", project_id AS ""projectId"",
                       device_fingerprint AS ""deviceFingerprint"",
                       source, created_at AS ""timestamp""
                FROM leads
                ORDER BY created_at DESC";

            await using var conn = new NpgsqlConnection(_connectionString);
            return await conn.QueryAsync<dynamic>(sql);
        }

        public async Task<bool> DeleteAsync(int id)
        {
            const string sql = "DELETE FROM leads WHERE id = @id";
            await using var conn = new NpgsqlConnection(_connectionString);
            var affected = await conn.ExecuteAsync(sql, new { id });
            return affected > 0;
        }
    }
}
