using Dapper;
using HyderabadUrbanReality.Core.Interfaces;
using HyderabadUrbanReality.Infrastructure.Repositories;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Npgsql;
using System.Security.Claims;
using System.Text.Json;

namespace HyderabadUrbanReality.Controllers
{
    /// <summary>
    /// Admin CRUD: user management + property management backed by PostgreSQL.
    /// All endpoints require Authorize — AdminGuard in Angular further restricts to admin role.
    /// </summary>
    [ApiController]
    [Route("api/admin")]
    [Authorize]
    public class AdminManagementController : ControllerBase
    {
        private readonly IUserRepository    _userRepo;
        private readonly IProjectRepository _projectRepo;
        private readonly LeadRepository     _leadRepo;
        private readonly IConfiguration     _config;
        private readonly ILogger<AdminManagementController> _logger;

        public AdminManagementController(
            IUserRepository userRepo,
            IProjectRepository projectRepo,
            LeadRepository leadRepo,
            IConfiguration config,
            ILogger<AdminManagementController> logger)
        {
            _userRepo    = userRepo;
            _projectRepo = projectRepo;
            _leadRepo    = leadRepo;
            _config      = config;
            _logger      = logger;
        }

        // ─────────────────────────────────────────────────────────────────────
        // USER MANAGEMENT
        // ─────────────────────────────────────────────────────────────────────

        /// GET /api/admin/users?page=1&pageSize=50
        [HttpGet("users")]
        public async Task<IActionResult> GetUsers([FromQuery] int page = 1, [FromQuery] int pageSize = 50)
        {
            var users = await _userRepo.GetAllUsersAsync(page, pageSize);
            var total = await _userRepo.GetUserCountAsync();
            var list  = users.Select(u => new
            {
                u.Id, u.Email, u.FullName, u.Mobile, u.Role,
                u.IsVerified, u.IsActive, u.LastLoginAt, u.CreatedAt
            });
            return Ok(new { users = list, total, page, pageSize });
        }

        /// GET /api/admin/users/{id}
        [HttpGet("users/{id:guid}")]
        public async Task<IActionResult> GetUser(Guid id)
        {
            var user = await _userRepo.GetByIdAsync(id);
            if (user is null) return NotFound(new { error = "user_not_found" });
            return Ok(new {
                user.Id, user.Email, user.FullName, user.Mobile, user.Role,
                user.IsVerified, user.IsActive, user.LastLoginAt, user.CreatedAt
            });
        }

        /// PUT /api/admin/users/{id}/role  — body: { "role": "admin" | "user" }
        [HttpPut("users/{id:guid}/role")]
        public async Task<IActionResult> UpdateUserRole(Guid id, [FromBody] UpdateRoleRequest dto)
        {
            if (dto.Role != "admin" && dto.Role != "user")
                return BadRequest(new { error = "invalid_role", message = "Role must be 'admin' or 'user'" });

            // Prevent self-demotion
            var callerId = GetCallerId();
            if (callerId == id && dto.Role != "admin")
                return BadRequest(new { error = "cannot_demote_self" });

            await _userRepo.UpdateUserRoleAsync(id, dto.Role);
            return Ok(new { message = $"User role updated to '{dto.Role}'" });
        }

        /// PUT /api/admin/users/{id}/status  — body: { "isActive": true | false }
        [HttpPut("users/{id:guid}/status")]
        public async Task<IActionResult> UpdateUserStatus(Guid id, [FromBody] UpdateStatusRequest dto)
        {
            var callerId = GetCallerId();
            if (callerId == id && !dto.IsActive)
                return BadRequest(new { error = "cannot_deactivate_self" });

            await _userRepo.UpdateUserStatusAsync(id, dto.IsActive);
            return Ok(new { message = dto.IsActive ? "User activated" : "User deactivated" });
        }

        /// DELETE /api/admin/users/{id}
        [HttpDelete("users/{id:guid}")]
        public async Task<IActionResult> DeleteUser(Guid id)
        {
            var callerId = GetCallerId();
            if (callerId == id)
                return BadRequest(new { error = "cannot_delete_self" });

            var user = await _userRepo.GetByIdAsync(id);
            if (user is null) return NotFound(new { error = "user_not_found" });

            await _userRepo.DeleteUserAsync(id);
            _logger.LogInformation("Admin deleted user {Id} ({Email})", id, user.Email);
            return NoContent();
        }

        /// GET /api/admin/users/stats
        [HttpGet("users/stats")]
        public async Task<IActionResult> GetUserStats()
        {
            var connStr = _config.GetConnectionString("DefaultConnection")!;
            await using var conn = new NpgsqlConnection(connStr);
            var stats = await conn.QuerySingleAsync(@"
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN is_active  THEN 1 ELSE 0 END) AS active,
                    SUM(CASE WHEN is_verified THEN 1 ELSE 0 END) AS verified,
                    SUM(CASE WHEN role = 'admin' THEN 1 ELSE 0 END) AS admins,
                    SUM(CASE WHEN created_at >= NOW() - INTERVAL '7 days' THEN 1 ELSE 0 END) AS new_this_week
                FROM users");
            return Ok(stats);
        }

        // ─────────────────────────────────────────────────────────────────────
        // PROPERTY MANAGEMENT
        // ─────────────────────────────────────────────────────────────────────

        /// GET /api/admin/properties — same as public but with admin context
        [HttpGet("properties")]
        public async Task<IActionResult> GetProperties()
        {
            var projects = await _projectRepo.GetAllProjectsAsync();
            return Ok(projects);
        }

        /// GET /api/admin/properties/{id}
        [HttpGet("properties/{id}")]
        public async Task<IActionResult> GetProperty(string id)
        {
            var project = await _projectRepo.GetProjectByIdAsync(id);
            if (project is null) return NotFound(new { error = "not_found" });
            return Ok(project);
        }

        /// POST /api/admin/properties — create new property
        [HttpPost("properties")]
        public async Task<IActionResult> CreateProperty([FromBody] Dictionary<string, JsonElement> body)
        {
            var data = body.ToDictionary(
                kv => kv.Key,
                kv => (object)(kv.Value.ValueKind == JsonValueKind.String ? kv.Value.GetString()! : kv.Value.GetRawText())
            );
            var newId = await _projectRepo.CreateProjectAsync(data);
            _logger.LogInformation("Admin created project {Id}", newId);
            return StatusCode(201, new { id = newId, message = "Property created" });
        }

        /// PUT /api/admin/properties/{id} — update property fields
        [HttpPut("properties/{id}")]
        public async Task<IActionResult> UpdateProperty(string id, [FromBody] Dictionary<string, JsonElement> body)
        {
            if (!await _projectRepo.ProjectExistsAsync(id))
                return NotFound(new { error = "not_found" });

            var updates = body.ToDictionary(
                kv => kv.Key,
                kv => (object)(kv.Value.ValueKind == JsonValueKind.String ? kv.Value.GetString()! : kv.Value.GetRawText())
            );
            var ok = await _projectRepo.UpdateProjectAsync(id, updates);
            if (!ok) return BadRequest(new { error = "no_updatable_fields" });
            _logger.LogInformation("Admin updated project {Id}", id);
            return Ok(new { message = "Property updated" });
        }

        /// DELETE /api/admin/properties/{id}
        [HttpDelete("properties/{id}")]
        public async Task<IActionResult> DeleteProperty(string id)
        {
            var ok = await _projectRepo.DeleteProjectAsync(id);
            if (!ok) return NotFound(new { error = "not_found" });
            _logger.LogInformation("Admin deleted project {Id}", id);
            return NoContent();
        }

        /// PUT /api/admin/properties/{id}/pricing — update pricing JSON
        [HttpPut("properties/{id}/pricing")]
        public async Task<IActionResult> UpdatePricing(string id, [FromBody] JsonElement pricing)
        {
            if (!await _projectRepo.ProjectExistsAsync(id))
                return NotFound(new { error = "not_found" });

            var connStr = _config.GetConnectionString("DefaultConnection")!;
            await using var conn = new NpgsqlConnection(connStr);
            await conn.ExecuteAsync(
                "UPDATE projects SET pricing = @pricing::jsonb, updated_at = NOW() WHERE id = @id",
                new { pricing = pricing.GetRawText(), id });
            return Ok(new { message = "Pricing updated" });
        }

        // ─────────────────────────────────────────────────────────────────────
        // LEADS
        // ─────────────────────────────────────────────────────────────────────

        /// GET /api/admin/leads?page=1&pageSize=50
        [HttpGet("leads")]
        public async Task<IActionResult> GetLeads([FromQuery] int page = 1, [FromQuery] int pageSize = 50)
        {
            var connStr = _config.GetConnectionString("DefaultConnection")!;
            await using var conn = new NpgsqlConnection(connStr);
            var sql = @"
                SELECT id, name, email, mobile,
                       area_of_interest AS ""areaOfInterest"",
                       project_name AS ""projectName"",
                       source, created_at AS ""createdAt""
                FROM leads
                ORDER BY created_at DESC
                LIMIT @pageSize OFFSET @offset";
            var leads = await conn.QueryAsync<dynamic>(sql, new { pageSize, offset = (page - 1) * pageSize });
            var total = await conn.ExecuteScalarAsync<int>("SELECT COUNT(*) FROM leads");
            return Ok(new { leads, total, page, pageSize });
        }

        /// DELETE /api/admin/leads/{id}
        [HttpDelete("leads/{id:int}")]
        public async Task<IActionResult> DeleteLead(int id)
        {
            var ok = await _leadRepo.DeleteAsync(id);
            if (!ok) return NotFound(new { error = "not_found" });
            return NoContent();
        }

        // ─────────────────────────────────────────────────────────────────────
        // DASHBOARD STATS
        // ─────────────────────────────────────────────────────────────────────

        /// GET /api/admin/dashboard
        [HttpGet("dashboard")]
        public async Task<IActionResult> GetDashboardStats()
        {
            var connStr = _config.GetConnectionString("DefaultConnection")!;
            await using var conn = new NpgsqlConnection(connStr);

            var stats = await conn.QuerySingleAsync(@"
                SELECT
                    (SELECT COUNT(*) FROM projects)    AS total_properties,
                    (SELECT COUNT(*) FROM users)        AS total_users,
                    (SELECT COUNT(*) FROM leads)        AS total_leads,
                    (SELECT COUNT(*) FROM users WHERE is_active = true) AS active_users,
                    (SELECT COUNT(*) FROM users WHERE created_at >= NOW() - INTERVAL '30 days') AS new_users_30d,
                    (SELECT COUNT(*) FROM leads WHERE created_at >= NOW() - INTERVAL '30 days') AS new_leads_30d
            ");
            return Ok(stats);
        }

        // ─────────────────────────────────────────────────────────────────────
        private Guid GetCallerId() =>
            Guid.Parse(User.FindFirstValue(ClaimTypes.NameIdentifier)
                ?? User.FindFirstValue("sub")
                ?? throw new InvalidOperationException("No user ID claim"));
    }

    public record UpdateRoleRequest(string Role);
    public record UpdateStatusRequest(bool IsActive);
}
