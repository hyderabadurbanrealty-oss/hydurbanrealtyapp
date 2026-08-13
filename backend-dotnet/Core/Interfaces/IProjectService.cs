namespace HyderabadUrbanReality.Core.Interfaces
{
    /// <summary>
    /// Defines contract for project business logic.
    /// </summary>
    public interface IProjectService
    {
        /// <summary>Gets all projects (served from cache when warm).</summary>
        Task<IEnumerable<Dictionary<string, object>>> GetAllProjectsAsync();

        /// <summary>Gets a specific project by ID (served from cache when warm).</summary>
        Task<Dictionary<string, object>?> GetProjectByIdAsync(string projectId);

        /// <summary>Invalidates the full project list cache (call after scrape/admin writes).</summary>
        void InvalidateAll();

        /// <summary>Invalidates cache for a single project and the list.</summary>
        void InvalidateProject(string projectId);
    }
}
