namespace HyderabadUrbanReality.Core.Interfaces
{
    /// <summary>
    /// Defines contract for project data operations
    /// Follows Interface Segregation Principle - focused on project operations only
    /// </summary>
    public interface IProjectRepository
    {
        /// <summary>
        /// Retrieves all projects from the data source
        /// </summary>
        Task<IEnumerable<Dictionary<string, object>>> GetAllProjectsAsync();
        
        /// <summary>
        /// Retrieves a specific project by ID
        /// </summary>
        Task<Dictionary<string, object>?> GetProjectByIdAsync(string projectId);
        
        /// <summary>
        /// Checks if a project exists
        /// </summary>
        Task<bool> ProjectExistsAsync(string projectId);

        /// <summary>
        /// Retrieves all projects matching the given PIN code
        /// </summary>
        Task<IEnumerable<Dictionary<string, object>>> GetProjectsByPinCodeAsync(string pinCode);

        // ── Admin project CRUD ────────────────────────────────────────────────
        Task<bool> UpdateProjectAsync(string projectId, Dictionary<string, object> updates);
        Task<bool> DeleteProjectAsync(string projectId);
        Task<string> CreateProjectAsync(Dictionary<string, object> projectData);
    }
}
