using Dapper;
using HyderabadUrbanReality.Core.Interfaces;
using Npgsql;
using System.Text.Json;

namespace HyderabadUrbanReality.Infrastructure.Repositories
{
    /// <summary>
    /// PostgreSQL-backed implementation of IProjectRepository using Npgsql + Dapper.
    /// Activated via the FeatureFlags:UsePostgresRepository configuration flag.
    /// Returns 503 Service Unavailable (via ServiceUnavailableException) when the
    /// database cannot be reached, so the controller layer can return the appropriate HTTP status.
    /// </summary>
    public class PostgresProjectRepository : IProjectRepository
    {
        private readonly string _connectionString;
        private readonly ILogger<PostgresProjectRepository> _logger;

        public PostgresProjectRepository(
            IConfiguration configuration,
            ILogger<PostgresProjectRepository> logger)
        {
            _connectionString = configuration.GetConnectionString("DefaultConnection")
                ?? throw new InvalidOperationException("ConnectionStrings:DefaultConnection is not configured.");
            _logger = logger;
        }

        private async Task<T> WithRetryAsync<T>(Func<Task<T>> operation, string operationName)
        {
            const int maxAttempts = 3;
            for (int attempt = 1; attempt <= maxAttempts; attempt++)
            {
                try
                {
                    return await operation();
                }
                catch (NpgsqlException ex) when (attempt < maxAttempts &&
                    (ex.Message.Contains("Timeout") || ex.Message.Contains("stream") ||
                     ex.Message.Contains("connection") || ex.InnerException is System.TimeoutException))
                {
                    _logger.LogWarning("DB transient error on attempt {Attempt}/{Max} for {Op}: {Msg}",
                        attempt, maxAttempts, operationName, ex.Message);
                    // Clear the connection pool so next attempt gets a fresh connection
                    NpgsqlConnection.ClearAllPools();
                    await Task.Delay(TimeSpan.FromMilliseconds(500 * attempt));
                }
            }
            throw new ServiceUnavailableException("Database unavailable after retries");
        }

        /// <inheritdoc />
        public async Task<IEnumerable<Dictionary<string, object>>> GetAllProjectsAsync()
        {
            const string sql = @"
                SELECT id, project_name, project_status, project_type,
                       district, mandal, locality, pin_code, village,
                       approved_date, completion_date, revised_completion_date,
                       total_area_sqmt, net_area_sqmt, built_up_area_sqmt, mortgage_area_sqmt,
                       promoter_name, org_type, bank_name, branch_name,
                       plan_approval_number, survey_number,
                       is_msb, has_litigation,
                       total_flats, total_booked, saleable_area_sqmt,
                       raw_data::text   AS raw_data,
                       pricing::text    AS pricing,
                       available_documents,
                       scraped_at, updated_at
                FROM   projects
                ORDER  BY project_name";

            try
            {
                return await WithRetryAsync(async () =>
                {
                    await using var conn = new NpgsqlConnection(_connectionString);
                    var rows = await conn.QueryAsync<dynamic>(sql);
                    return rows.Select(MapToProjectDict).ToList();
                }, nameof(GetAllProjectsAsync));
            }
            catch (ServiceUnavailableException) { throw; }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Database connection failed in GetAllProjectsAsync");
                throw new ServiceUnavailableException("Database unavailable");
            }
        }

        /// <inheritdoc />
        public async Task<Dictionary<string, object>?> GetProjectByIdAsync(string projectId)
        {
            const string sql = @"
                SELECT id, project_name, project_status, project_type,
                       district, mandal, locality, pin_code, village,
                       approved_date, completion_date, revised_completion_date,
                       total_area_sqmt, net_area_sqmt, built_up_area_sqmt, mortgage_area_sqmt,
                       promoter_name, org_type, bank_name, branch_name,
                       plan_approval_number, survey_number,
                       is_msb, has_litigation,
                       total_flats, total_booked, saleable_area_sqmt,
                       raw_data::text   AS raw_data,
                       pricing::text    AS pricing,
                       available_documents,
                       scraped_at, updated_at
                FROM   projects
                WHERE  id = @id OR project_name = @id";

            try
            {
                await using var conn = new NpgsqlConnection(_connectionString);
                var row = await conn.QuerySingleOrDefaultAsync<dynamic>(sql, new { id = projectId });
                return row is null ? null : MapToProjectDict(row);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Database connection failed in GetProjectByIdAsync for id={Id}", projectId);
                throw new ServiceUnavailableException("Database unavailable");
            }
        }

        /// <inheritdoc />
        public async Task<bool> ProjectExistsAsync(string projectId)
        {
            const string sql = "SELECT COUNT(1) FROM projects WHERE id = @id OR project_name = @id";

            try
            {
                await using var conn = new NpgsqlConnection(_connectionString);
                var count = await conn.ExecuteScalarAsync<int>(sql, new { id = projectId });
                return count > 0;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Database connection failed in ProjectExistsAsync for id={Id}", projectId);
                throw new ServiceUnavailableException("Database unavailable");
            }
        }

        /// <inheritdoc />
        public async Task<IEnumerable<Dictionary<string, object>>> GetProjectsByPinCodeAsync(string pinCode)
        {
            const string sql = @"
                SELECT id, project_name, project_status, project_type,
                       district, mandal, locality, pin_code, village,
                       approved_date, completion_date, revised_completion_date,
                       total_area_sqmt, net_area_sqmt, built_up_area_sqmt, mortgage_area_sqmt,
                       promoter_name, org_type, bank_name, branch_name,
                       plan_approval_number, survey_number,
                       is_msb, has_litigation,
                       total_flats, total_booked, saleable_area_sqmt,
                       raw_data::text   AS raw_data,
                       pricing::text    AS pricing,
                       available_documents,
                       scraped_at, updated_at
                FROM   projects
                WHERE  pin_code = @pinCode
                ORDER  BY project_name";

            try
            {
                await using var conn = new NpgsqlConnection(_connectionString);
                var rows = await conn.QueryAsync<dynamic>(sql, new { pinCode });
                return rows.Select(MapToProjectDict).ToList();
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Database connection failed in GetProjectsByPinCodeAsync for pinCode={PinCode}", pinCode);
                throw new ServiceUnavailableException("Database unavailable");
            }
        }

        /// <inheritdoc />
        public async Task<bool> UpdateProjectAsync(string projectId, Dictionary<string, object> updates)
        {
            // Build dynamic SET clause from updates dict — only allow safe field names
            var allowed = new HashSet<string> {
                "project_name","project_status","project_type","district","mandal",
                "locality","pin_code","village","promoter_name","org_type",
                "bank_name","branch_name","plan_approval_number","survey_number",
                "total_flats","total_booked","pricing"
            };
            var setClauses = updates.Keys
                .Where(k => allowed.Contains(k.ToLower()))
                .Select(k => $"{k.ToLower()} = @{k.Replace(" ", "_")}").ToList();
            if (!setClauses.Any()) return false;

            setClauses.Add("updated_at = NOW()");
            var sql = $"UPDATE projects SET {string.Join(", ", setClauses)} WHERE id = @id";

            var dp = new DynamicParameters();
            dp.Add("id", projectId);
            foreach (var kv in updates)
                if (allowed.Contains(kv.Key.ToLower()))
                    dp.Add(kv.Key.Replace(" ", "_"), kv.Value?.ToString());

            await using var conn = new NpgsqlConnection(_connectionString);
            var affected = await conn.ExecuteAsync(sql, dp);
            return affected > 0;
        }

        /// <inheritdoc />
        public async Task<bool> DeleteProjectAsync(string projectId)
        {
            const string sql = "DELETE FROM projects WHERE id = @id";
            await using var conn = new NpgsqlConnection(_connectionString);
            var affected = await conn.ExecuteAsync(sql, new { id = projectId });
            return affected > 0;
        }

        /// <inheritdoc />
        public async Task<string> CreateProjectAsync(Dictionary<string, object> projectData)
        {
            var projectId = projectData.TryGetValue("id", out var idVal)
                ? idVal?.ToString() ?? Guid.NewGuid().ToString()
                : (projectData.TryGetValue("Project Name", out var nameVal)
                    ? System.Text.RegularExpressions.Regex.Replace(nameVal?.ToString() ?? "", @"[<>:""/\\|?*]", "_")
                    : Guid.NewGuid().ToString());

            var rawData = System.Text.Json.JsonSerializer.Serialize(projectData);

            const string sql = @"
                INSERT INTO projects (id, project_name, project_status, project_type,
                    district, mandal, locality, pin_code, total_flats, raw_data, scraped_at)
                VALUES (@id, @projectName, @projectStatus, @projectType,
                    @district, @mandal, @locality, @pinCode, @totalFlats, @rawData::jsonb, NOW())
                ON CONFLICT (id) DO UPDATE SET
                    raw_data   = EXCLUDED.raw_data,
                    updated_at = NOW()";

            var dp = new DynamicParameters();
            dp.Add("id",            projectId);
            dp.Add("projectName",   GetStr(projectData, "Project Name", "project_name"));
            dp.Add("projectStatus", GetStr(projectData, "Project Status", "project_status") ?? "New");
            dp.Add("projectType",   GetStr(projectData, "Project Type", "project_type") ?? "Residential");
            dp.Add("district",      GetStr(projectData, "District", "district"));
            dp.Add("mandal",        GetStr(projectData, "Mandal", "mandal"));
            dp.Add("locality",      GetStr(projectData, "Locality", "locality"));
            dp.Add("pinCode",       GetStr(projectData, "Pin Code", "pin_code"));
            dp.Add("totalFlats",    int.TryParse(GetStr(projectData, "totalFlats", "total_flats"), out var tf) ? tf : 0);
            dp.Add("rawData",       rawData);

            await using var conn = new NpgsqlConnection(_connectionString);
            await conn.ExecuteAsync(sql, dp);
            return projectId;
        }

        private static string? GetStr(Dictionary<string, object> d, params string[] keys)
        {
            foreach (var k in keys)
                if (d.TryGetValue(k, out var v) && v is not null) return v.ToString();
            return null;
        }

        private static Dictionary<string, object> MapToProjectDict(dynamic row)
        {
            var dict = new Dictionary<string, object>();
            var rowDict = (IDictionary<string, object>)row;

            foreach (var kv in rowDict)
            {
                if (kv.Value is not null)
                    dict[kv.Key] = kv.Value;
            }

            // ── Deserialise raw_data and FLATTEN it to the top level ──────────
            // The old file-based repo returned view_page_data.json directly so
            // all keys like "Project Name", "Total Area(In sqmts)", "Floor Breakdown"
            // were at the root.  We replicate that by deep-flattening here.
            if (dict.TryGetValue("raw_data", out var rawDataObj) && rawDataObj is string rawDataStr)
            {
                try
                {
                    var parsed = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(rawDataStr);
                    if (parsed is not null)
                    {
                        dict["raw_data"] = parsed;

                        // Build a case-insensitive set of existing keys to avoid duplicates
                        var existingLower = dict.Keys
                            .Select(k => k.ToLowerInvariant())
                            .ToHashSet();

                        // First pass: add top-level keys from raw_data
                        foreach (var kv in parsed)
                        {
                            if (!existingLower.Contains(kv.Key.ToLowerInvariant()))
                            {
                                // Store section objects as-is; extract primitive values as strings
                                object firstVal = kv.Value.ValueKind switch
                                {
                                    JsonValueKind.String => kv.Value.GetString() ?? "",
                                    JsonValueKind.Number => kv.Value.GetRawText(),
                                    JsonValueKind.True   => true,
                                    JsonValueKind.False  => false,
                                    _                    => (object)kv.Value  // arrays/objects kept as JsonElement
                                };
                                dict[kv.Key] = firstVal;
                                existingLower.Add(kv.Key.ToLowerInvariant());
                            }
                        }

                        // Second pass: unpack nested section objects
                        // This surfaces "Total Area(In sqmts)", "Project Type" etc.
                        // that live inside "General Information", "Land Details" etc.
                        foreach (var kv in parsed)
                        {
                            if (kv.Value.ValueKind == JsonValueKind.Object)
                            {
                                foreach (var inner in kv.Value.EnumerateObject())
                                {
                                    if (!existingLower.Contains(inner.Name.ToLowerInvariant()))
                                    {
                                        // Extract primitive values as strings so Angular gets plain values
                                        object val = inner.Value.ValueKind switch
                                        {
                                            JsonValueKind.String => inner.Value.GetString() ?? "",
                                            JsonValueKind.Number => inner.Value.GetRawText(),
                                            JsonValueKind.True   => true,
                                            JsonValueKind.False  => false,
                                            _                    => inner.Value
                                        };
                                        dict[inner.Name] = val;
                                        existingLower.Add(inner.Name.ToLowerInvariant());
                                    }
                                }
                            }
                            // Also flatten top-level primitives as plain values
                            else if (!existingLower.Contains(kv.Key.ToLowerInvariant()))
                            {
                                object topVal = kv.Value.ValueKind switch
                                {
                                    JsonValueKind.String => kv.Value.GetString() ?? "",
                                    JsonValueKind.Number => kv.Value.GetRawText(),
                                    JsonValueKind.True   => true,
                                    JsonValueKind.False  => false,
                                    _                    => kv.Value
                                };
                                dict[kv.Key] = topVal;
                                existingLower.Add(kv.Key.ToLowerInvariant());
                            }
                        }
                    }
                }
                catch (JsonException)
                {
                    // Leave as string if parsing fails
                }
            }

            // ── Structured column aliases (camelCase for frontend) ────────────
            if (dict.TryGetValue("project_name", out var pn))              dict["projectName"]           = pn;
            if (dict.TryGetValue("project_status", out var ps))            dict["projectStatus"]         = ps;
            if (dict.TryGetValue("project_type", out var pt))              dict["projectType"]           = pt;
            if (dict.TryGetValue("pin_code", out var pc))                  dict["pinCode"]               = pc;
            if (dict.TryGetValue("total_flats", out var tf))               dict["totalFlats"]            = tf;
            if (dict.TryGetValue("total_booked", out var tb))              dict["totalBookedFlats"]      = tb;
            if (dict.TryGetValue("approved_date", out var ad))             dict["approvedDate"]          = ad;
            if (dict.TryGetValue("completion_date", out var cd))           dict["completionDate"]        = cd;
            if (dict.TryGetValue("revised_completion_date", out var rcd))  dict["revisedCompletionDate"] = rcd;
            if (dict.TryGetValue("plan_approval_number", out var pan))     dict["planApprovalNumber"]    = pan;
            if (dict.TryGetValue("survey_number", out var sn))             dict["surveyNumber"]          = sn;
            if (dict.TryGetValue("promoter_name", out var prn))            dict["promoterName"]          = prn;
            if (dict.TryGetValue("org_type", out var ot))                  dict["orgType"]               = ot;
            if (dict.TryGetValue("bank_name", out var bn))                 dict["bankName"]              = bn;
            if (dict.TryGetValue("branch_name", out var brn))              dict["branchName"]            = brn;
            if (dict.TryGetValue("total_area_sqmt", out var tas))          dict["totalAreaSqmt"]         = tas;
            if (dict.TryGetValue("net_area_sqmt", out var nas))            dict["netAreaSqmt"]           = nas;
            if (dict.TryGetValue("built_up_area_sqmt", out var bas))       dict["builtUpAreaSqmt"]       = bas;
            if (dict.TryGetValue("mortgage_area_sqmt", out var mas))       dict["mortgageAreaSqmt"]      = mas;
            if (dict.TryGetValue("saleable_area_sqmt", out var sas))       dict["saleableAreaSqmt"]      = sas;
            if (dict.TryGetValue("is_msb", out var msb))                   dict["isMsb"]                 = msb;
            if (dict.TryGetValue("has_litigation", out var hl))            dict["hasLitigation"]         = hl;
            if (dict.TryGetValue("available_documents", out var avd))      dict["availableDocuments"]    = avd;
            if (dict.TryGetValue("scraped_at", out var sa))                dict["scrapedAt"]             = sa;
            if (dict.TryGetValue("updated_at", out var ua))                dict["updatedAt"]             = ua;

            return dict;
        }
    }

    /// <summary>
    /// Thrown by PostgresProjectRepository when the database connection cannot be
    /// established. Controllers should catch this and return 503 Service Unavailable.
    /// </summary>
    public class ServiceUnavailableException : Exception
    {
        public ServiceUnavailableException(string message) : base(message) { }
    }
}
