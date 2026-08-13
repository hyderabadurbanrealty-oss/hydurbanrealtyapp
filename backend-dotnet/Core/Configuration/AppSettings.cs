namespace HyderabadUrbanReality.Core.Configuration
{
    /// <summary>
    /// Configuration settings for the application
    /// Follows Single Responsibility - handles app settings only
    /// </summary>
    public class AppSettings
    {
        public string UploadFolder { get; set; } = "uploads";
        public long MaxFileSize { get; set; } = 10485760; // 10MB
        public long MaxImageSize { get; set; } = 5242880; // 5MB
        public string ScrapedProjectsPath { get; set; } = "../scraped_projects";
        public string AdminUsername { get; set; } = "admin";
        public string AdminPasswordHash { get; set; } = "$2a$11$N9qo8uLOickgx2ZMRZoMye/h5fP8Q2.O2rNqh/pEWNQ0Vqx3Zg1Oy"; // BCrypt hash for "admin123"
        public string JwtSecret { get; set; } = "HyderabadUrbanReality-SecureKey-2026-MinimumLength32"; // Min 32 chars
        public string AllowedOrigins { get; set; } = "http://localhost:4200";
        public string[] AllowedFileExtensions { get; set; } = { "pdf", "doc", "docx", "jpg", "jpeg", "png", "gif" };
        public ReraSettings ReraSettings { get; set; } = new ReraSettings();
    }

    /// <summary>
    /// Configuration for RERA website scraping
    /// </summary>
    public class ReraSettings
    {
        public string BaseUrl { get; set; } = "https://rerait.telangana.gov.in";
        public string SearchPageUrl { get; set; } = "https://rerait.telangana.gov.in/SearchList/Search";
        public string CaptchaUrl { get; set; } = "https://rerait.telangana.gov.in/SearchList/SearchCaptcha";
        public int MaxRetries { get; set; } = 3;
        public int TimeoutSeconds { get; set; } = 30;
        public List<string> AvailableDistricts { get; set; } = new List<string> { "Hyderabad", "Ranga Reddy", "Sangareddy" };
        public string DefaultDistrict { get; set; } = "Hyderabad";
    }

    /// <summary>
    /// Configuration for OpenStreetMap API
    /// </summary>
    public class OpenStreetMapSettings
    {
        public string OverpassUrl      { get; set; } = "https://overpass-api.de/api/interpreter";
        public string NominatimUrl     { get; set; } = "https://nominatim.openstreetmap.org/search";
        public int    DefaultRadiusKm  { get; set; } = 3;
        public double RateLimitSeconds { get; set; } = 1.0;
        // Used by OpenStreetMapService constructor
        public int    TimeoutSeconds   { get; set; } = 30;
        public string UserAgent        { get; set; } = "HyderabadUrbanReality/1.0 (contact: admin@hydurban.in)";
    }

    /// <summary>
    /// Configuration for Selenium WebDriver
    /// </summary>
    public class SeleniumSettings
    {
        public bool Headless { get; set; } = true;
        public int ImplicitWaitSeconds { get; set; } = 10;
        public int PageLoadTimeoutSeconds { get; set; } = 30;
        public string WindowSize { get; set; } = "1920,1080";
    }
}
