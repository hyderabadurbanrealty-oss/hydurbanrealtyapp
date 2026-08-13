namespace HyderabadUrbanReality.Core.DTOs
{
    public class FileUploadResponseDto
    {
        public bool Success { get; set; }
        public string Message { get; set; } = string.Empty;
        public string FileName { get; set; } = string.Empty;
        public string FilePath { get; set; } = string.Empty;
        public string Status { get; set; } = string.Empty;
        public long FileSize { get; set; }
    }
}