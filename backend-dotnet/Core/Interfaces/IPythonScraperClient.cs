namespace HyderabadUrbanReality.Core.Interfaces
{
    /// <summary>
    /// Interface for communicating with Python Flask scraper service
    /// Follows Dependency Inversion - depend on abstraction, not concrete implementation
    /// </summary>
    public interface IPythonScraperClient
    {
        /// <summary>
        /// Gets all scraped projects from Python Flask API
        /// </summary>
        Task<IEnumerable<Dictionary<string, object>>> GetScrapedProjectsAsync();

        /// <summary>
        /// Gets a specific scraped project by ID from Python Flask API
        /// </summary>
        Task<Dictionary<string, object>?> GetScrapedProjectByIdAsync(string projectId);

        /// <summary>
        /// Triggers Python scraper to scrape a specific project
        /// </summary>
        Task<bool> ScrapeProjectAsync(string projectName);

        /// <summary>
        /// Triggers Python scraper to fetch all project names from RERA
        /// </summary>
        Task<bool> FetchAllProjectNamesAsync();

        /// <summary>
        /// Triggers bulk scraping of all projects starting from a specific index
        /// </summary>
        Task<bool> BulkScrapeProjectsAsync(int startIndex = 0);

        /// <summary>
        /// Checks if Python Flask service is available
        /// </summary>
        Task<bool> IsServiceAvailableAsync();

        /// <summary>
        /// Gets the current pincode/locality scrape preferences
        /// </summary>
        Task<Dictionary<string, object>> GetScrapePreferencesAsync();

        /// <summary>
        /// Saves pincode/locality scrape preferences
        /// </summary>
        Task<bool> SaveScrapePreferencesAsync(Dictionary<string, object> preferences);

        // ── SRO Transaction Data ─────────────────────────────────────────────

        /// <summary>City-wide quarterly aggregation proxied from Python.</summary>
        Task<string> GetSroCityAggregateAsync();

        /// <summary>Per-locality quarterly aggregation; optional locality filter.</summary>
        Task<string> GetSroLocalityAggregateAsync(string? locality);

        /// <summary>Top N localities by avg price/sqft for a given quarter.</summary>
        Task<string> GetSroPriceRankAsync(string? quarter, int top);

        /// <summary>Top N localities by total volume for a given quarter.</summary>
        Task<string> GetSroVolumeRankAsync(string? quarter, int top);

        /// <summary>SRO scrape status from Python.</summary>
        Task<string> GetSroScrapeStatusAsync();

        /// <summary>Start SRO scrape on Python.</summary>
        Task<string> StartSroScrapeAsync(string jsonPayload);

        // ── Ready Reckoner (Unit Rate) Scraping ──────────────────────────────

        /// <summary>RR scrape status from Python.</summary>
        Task<string> GetRrScrapeStatusAsync();

        /// <summary>Start RR scrape on Python.</summary>
        Task<string> StartRrScrapeAsync(string jsonPayload);

        /// <summary>Stop RR scrape on Python.</summary>
        Task<string> StopRrScrapeAsync();

        /// <summary>Quarterly SRO transaction trend for a single RERA project (fuzzy-matched by name).</summary>
        Task<string> GetSroProjectTrendAsync(string name);

        /// <summary>SRO registration/sales unit count for a single RERA project (fuzzy-matched by name).</summary>
        Task<string> GetSroProjectUnitsAsync(string name);

        /// <summary>Triggers bulk RERA scrape and returns Flask response.</summary>
        Task<string> TriggerBulkScrapeAsync(int startIndex);

        /// <summary>Triggers SRO scrape with optional SRO name and year filters.</summary>
        Task<string> TriggerSroScrapeAsync(string[] sros, int[] years);

        /// <summary>Triggers Ready Reckoner scrape with optional pincode filter.</summary>
        Task<string> TriggerRrScrapeAsync(string[] pincodes);

        /// <summary>Gets current scraping status from Flask.</summary>
        Task<string> GetScrapingStatusAsync();
    }
}
