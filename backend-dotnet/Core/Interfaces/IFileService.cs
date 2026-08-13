namespace HyderabadUrbanReality.Core.Interfaces
{
    /// <summary>
    /// Defines contract for file operations
    /// Follows Single Responsibility Principle
    /// </summary>
    public interface IFileService
    {
        /// <summary>
        /// Uploads file to storage
        /// </summary>
        Task<string> UploadFileAsync(Stream fileStream, string fileName);
        
        /// <summary>
        /// Validates file type and size
        /// </summary>
        bool ValidateFile(string fileName, long fileSize);
        
        /// <summary>
        /// Deletes a file
        /// </summary>
        Task<bool> DeleteFileAsync(string fileName);
    }
}
