using HyderabadUrbanReality.Core.Interfaces;
using Microsoft.Extensions.Caching.Memory;

namespace HyderabadUrbanReality.Application.Services
{
    /// <summary>
    /// Business logic service for project operations.
    /// Wraps the repository with IMemoryCache to avoid hitting disk/DB on every request.
    ///
    /// Cache strategy:
    ///   • All-projects list  → 30-minute absolute expiry, sliding 10-min window
    ///   • Individual project → 60-minute absolute expiry (changes rarely)
    ///   • Cache is invalidated on any write (update/delete/create) via InvalidateAll()
    /// </summary>
    public class ProjectService : IProjectService
    {
        private readonly IProjectRepository _repo;
        private readonly IMemoryCache       _cache;
        private readonly ILogger<ProjectService> _logger;

        // ── Cache keys ────────────────────────────────────────────────────
        private const string ALL_PROJECTS_KEY = "projects:all";
        private static string ProjectKey(string id) => $"projects:{id}";

        // ── TTL constants ─────────────────────────────────────────────────
        private static readonly TimeSpan AllProjectsAbsolute = TimeSpan.FromMinutes(30);
        private static readonly TimeSpan AllProjectsSliding  = TimeSpan.FromMinutes(10);
        private static readonly TimeSpan SingleProjectAbsolute = TimeSpan.FromMinutes(60);

        public ProjectService(
            IProjectRepository repo,
            IMemoryCache cache,
            ILogger<ProjectService> logger)
        {
            _repo   = repo   ?? throw new ArgumentNullException(nameof(repo));
            _cache  = cache  ?? throw new ArgumentNullException(nameof(cache));
            _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        }

        // ── GetAllProjectsAsync ───────────────────────────────────────────
        public async Task<IEnumerable<Dictionary<string, object>>> GetAllProjectsAsync()
        {
            if (_cache.TryGetValue(ALL_PROJECTS_KEY,
                    out IEnumerable<Dictionary<string, object>>? cached) && cached is not null)
            {
                _logger.LogDebug("Cache HIT — projects:all ({Count} items)", cached.Count());
                return cached;
            }

            _logger.LogInformation("Cache MISS — loading all projects from repository");
            var projects = await _repo.GetAllProjectsAsync();
            var list = projects.ToList(); // materialise once

            var opts = new MemoryCacheEntryOptions()
                .SetAbsoluteExpiration(AllProjectsAbsolute)
                .SetSlidingExpiration(AllProjectsSliding);

            _cache.Set(ALL_PROJECTS_KEY, (IEnumerable<Dictionary<string, object>>)list, opts);
            _logger.LogInformation("Cached {Count} projects (TTL {TTL} min)", list.Count, AllProjectsAbsolute.TotalMinutes);

            return list;
        }

        // ── GetProjectByIdAsync ───────────────────────────────────────────
        public async Task<Dictionary<string, object>?> GetProjectByIdAsync(string projectId)
        {
            if (string.IsNullOrWhiteSpace(projectId))
                throw new ArgumentException("Project ID cannot be null or empty", nameof(projectId));

            var key = ProjectKey(projectId);

            if (_cache.TryGetValue(key, out Dictionary<string, object>? cached))
            {
                _logger.LogDebug("Cache HIT — {Key}", key);
                return cached;
            }

            _logger.LogInformation("Cache MISS — loading project {Id} from repository", projectId);
            var project = await _repo.GetProjectByIdAsync(projectId);

            if (project is not null)
            {
                var opts = new MemoryCacheEntryOptions()
                    .SetAbsoluteExpiration(SingleProjectAbsolute);
                _cache.Set(key, project, opts);
            }

            return project;
        }

        // ── Cache invalidation ────────────────────────────────────────────
        /// <summary>
        /// Call after any write operation (admin update / delete / scrape refresh)
        /// to ensure stale data is never served.
        /// </summary>
        public void InvalidateAll()
        {
            _cache.Remove(ALL_PROJECTS_KEY);
            _logger.LogInformation("Project cache invalidated");
        }

        public void InvalidateProject(string projectId)
        {
            _cache.Remove(ProjectKey(projectId));
            _cache.Remove(ALL_PROJECTS_KEY); // list is now stale too
            _logger.LogInformation("Project cache invalidated for {Id}", projectId);
        }
    }
}
