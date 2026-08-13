using HyderabadUrbanReality.Core.Interfaces;
using HyderabadUrbanReality.Core.Configuration;
using Microsoft.Extensions.Options;

namespace HyderabadUrbanReality.Infrastructure.Services
{
    /// <summary>
    /// Service for file operations
    /// Follows Single Responsibility - handles file operations only
    /// </summary>
    public class FileService : IFileService
    {
        private readonly AppSettings _appSettings;
        private readonly ILogger<FileService> _logger;
        private readonly string _uploadFolder;

        public FileService(
            IOptions<AppSettings> appSettings,
            ILogger<FileService> logger)
        {
            _appSettings = appSettings?.Value ?? throw new ArgumentNullException(nameof(appSettings));
            _logger = logger ?? throw new ArgumentNullException(nameof(logger));
            
            _uploadFolder = Path.Combine(Directory.GetCurrentDirectory(), _appSettings.UploadFolder);
            
            // Ensure upload directory exists
            if (!Directory.Exists(_uploadFolder))
            {
                Directory.CreateDirectory(_uploadFolder);
                _logger.LogInformation("Created upload folder: {Folder}", _uploadFolder);
            }
        }

        /// <inheritdoc />
        public async Task<string> UploadFileAsync(Stream fileStream, string fileName)
        {
            if (fileStream == null)
            {
                throw new ArgumentNullException(nameof(fileStream));
            }

            if (string.IsNullOrWhiteSpace(fileName))
            {
                throw new ArgumentException("File name cannot be empty", nameof(fileName));
            }

            try
            {
                // Sanitize file name to prevent directory traversal attacks
                var sanitizedFileName = Path.GetFileName(fileName);
                var uniqueFileName = $"{Guid.NewGuid()}_{sanitizedFileName}";
                var filePath = Path.Combine(_uploadFolder, uniqueFileName);

                using (var fileStreamOutput = new FileStream(filePath, FileMode.Create))
                {
                    await fileStream.CopyToAsync(fileStreamOutput);
                }

                _logger.LogInformation("File uploaded successfully: {FileName}", uniqueFileName);
                return uniqueFileName;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error uploading file: {FileName}", fileName);
                throw;
            }
        }

        /// <inheritdoc />
        public bool ValidateFile(string fileName, long fileSize)
        {
            if (string.IsNullOrWhiteSpace(fileName))
            {
                return false;
            }

            // Check file extension
            var extension = Path.GetExtension(fileName).TrimStart('.').ToLowerInvariant();
            if (!_appSettings.AllowedFileExtensions.Contains(extension))
            {
                _logger.LogWarning("Invalid file extension: {Extension}", extension);
                return false;
            }

            // Check file size
            var maxSize = extension switch
            {
                "jpg" or "jpeg" or "png" or "gif" => _appSettings.MaxImageSize,
                _ => _appSettings.MaxFileSize
            };

            if (fileSize > maxSize)
            {
                _logger.LogWarning("File size {Size} exceeds maximum {MaxSize}", fileSize, maxSize);
                return false;
            }

            return true;
        }

        /// <inheritdoc />
        public Task<bool> DeleteFileAsync(string fileName)
        {
            if (string.IsNullOrWhiteSpace(fileName))
            {
                return Task.FromResult(false);
            }

            try
            {
                var filePath = Path.Combine(_uploadFolder, fileName);
                
                if (File.Exists(filePath))
                {
                    File.Delete(filePath);
                    _logger.LogInformation("File deleted successfully: {FileName}", fileName);
                    return Task.FromResult(true);
                }

                return Task.FromResult(false);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error deleting file: {FileName}", fileName);
                return Task.FromResult(false);
            }
        }
    }
}
