using HyderabadUrbanReality.Core.Interfaces;
using System.Net.Http.Headers;

namespace HyderabadUrbanReality.Infrastructure.Services
{
    /// <summary>
    /// File storage service using Supabase Storage REST API.
    /// Replaces local disk FileService — files persist across Render redeploys.
    ///
    /// Config keys (set in Render environment):
    ///   SupabaseSettings:Url          — https://qjgwnbszmojzgwmafvuc.supabase.co
    ///   SupabaseSettings:ServiceKey   — supabase service_role key (not anon key)
    ///   SupabaseSettings:Bucket       — storage bucket name (e.g. "property-media")
    /// </summary>
    public class SupabaseStorageService : IFileService
    {
        private readonly IConfiguration _config;
        private readonly IHttpClientFactory _http;
        private readonly ILogger<SupabaseStorageService> _logger;
        private readonly string[] _allowedExtensions = { "jpg", "jpeg", "png", "gif", "pdf", "doc", "docx" };
        private readonly long _maxImageSize  = 5 * 1024 * 1024;   // 5 MB
        private readonly long _maxFileSize   = 10 * 1024 * 1024;  // 10 MB

        public SupabaseStorageService(
            IConfiguration config,
            IHttpClientFactory http,
            ILogger<SupabaseStorageService> logger)
        {
            _config = config;
            _http   = http;
            _logger = logger;
        }

        public async Task<string> UploadFileAsync(Stream fileStream, string fileName)
        {
            var supabaseUrl = _config["SupabaseSettings:Url"]?.TrimEnd('/');
            var serviceKey  = _config["SupabaseSettings:ServiceKey"] ?? "";
            var bucket      = _config["SupabaseSettings:Bucket"] ?? "property-media";

            if (string.IsNullOrEmpty(supabaseUrl) || string.IsNullOrEmpty(serviceKey))
                throw new InvalidOperationException("SupabaseSettings:Url and SupabaseSettings:ServiceKey must be configured.");

            var ext           = Path.GetExtension(fileName).TrimStart('.');
            var uniqueName    = $"{Guid.NewGuid()}.{ext}";
            var storagePath   = uniqueName; // flat path in bucket

            var uploadUrl = $"{supabaseUrl}/storage/v1/object/{bucket}/{storagePath}";

            var client = _http.CreateClient();
            client.DefaultRequestHeaders.Authorization =
                new AuthenticationHeaderValue("Bearer", serviceKey);
            client.DefaultRequestHeaders.Add("apikey", serviceKey);

            // Read stream into byte array (Supabase Storage requires Content-Length)
            byte[] bytes;
            using (var ms = new MemoryStream())
            {
                await fileStream.CopyToAsync(ms);
                bytes = ms.ToArray();
            }

            var content = new ByteArrayContent(bytes);
            content.Headers.ContentType = new MediaTypeHeaderValue(GetMimeType(ext));

            var response = await client.PostAsync(uploadUrl, content);

            if (!response.IsSuccessStatusCode)
            {
                var err = await response.Content.ReadAsStringAsync();
                _logger.LogError("Supabase Storage upload failed {Status}: {Error}", response.StatusCode, err);
                throw new InvalidOperationException($"Storage upload failed: {response.StatusCode} — {err}");
            }

            // Return the public URL
            var publicUrl = $"{supabaseUrl}/storage/v1/object/public/{bucket}/{storagePath}";
            _logger.LogInformation("Uploaded {FileName} → {Url}", fileName, publicUrl);
            return publicUrl;
        }

        public bool ValidateFile(string fileName, long fileSize)
        {
            var ext = Path.GetExtension(fileName).TrimStart('.').ToLowerInvariant();
            if (!_allowedExtensions.Contains(ext)) return false;
            var maxSize = (ext is "jpg" or "jpeg" or "png" or "gif") ? _maxImageSize : _maxFileSize;
            return fileSize <= maxSize;
        }

        public async Task<bool> DeleteFileAsync(string fileUrlOrName)
        {
            var supabaseUrl = _config["SupabaseSettings:Url"]?.TrimEnd('/');
            var serviceKey  = _config["SupabaseSettings:ServiceKey"] ?? "";
            var bucket      = _config["SupabaseSettings:Bucket"] ?? "property-media";

            if (string.IsNullOrEmpty(supabaseUrl) || string.IsNullOrEmpty(serviceKey))
                return false;

            // Extract just the file name / path from a full URL if needed
            var storagePath = fileUrlOrName;
            var marker = $"/object/public/{bucket}/";
            var idx = fileUrlOrName.IndexOf(marker, StringComparison.Ordinal);
            if (idx >= 0) storagePath = fileUrlOrName[(idx + marker.Length)..];

            var deleteUrl = $"{supabaseUrl}/storage/v1/object/{bucket}/{storagePath}";
            var client = _http.CreateClient();
            client.DefaultRequestHeaders.Authorization =
                new AuthenticationHeaderValue("Bearer", serviceKey);
            client.DefaultRequestHeaders.Add("apikey", serviceKey);

            var response = await client.DeleteAsync(deleteUrl);
            return response.IsSuccessStatusCode;
        }

        private static string GetMimeType(string ext) => ext.ToLowerInvariant() switch
        {
            "jpg" or "jpeg" => "image/jpeg",
            "png"           => "image/png",
            "gif"           => "image/gif",
            "pdf"           => "application/pdf",
            "doc"           => "application/msword",
            "docx"          => "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            _               => "application/octet-stream"
        };
    }
}
