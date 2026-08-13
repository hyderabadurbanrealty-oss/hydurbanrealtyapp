namespace HyderabadUrbanReality.Core.Interfaces
{
    /// <summary>
    /// Defines contract for OpenStreetMap operations
    /// Follows Single Responsibility and Interface Segregation Principles
    /// </summary>
    public interface IOpenStreetMapService
    {
        /// <summary>
        /// Gets neighborhood data for coordinates
        /// </summary>
        Task<Dictionary<string, object>> GetNeighborhoodDataAsync(double latitude, double longitude, string district);
        
        /// <summary>
        /// Geocodes an address to coordinates
        /// </summary>
        Task<(double latitude, double longitude)?> GeocodeAddressAsync(string address);
        
        /// <summary>
        /// Smart multi-strategy geocoding with fallback
        /// Tries multiple address combinations from most to least specific
        /// </summary>
        Task<(double latitude, double longitude)?> SmartGeocodeAsync(
            string houseNumber = "",
            string buildingName = "",
            string streetName = "",
            string locality = "",
            string mandal = "",
            string district = "",
            string pinCode = "");
        
        /// <summary>
        /// Fetches nearby schools
        /// </summary>
        Task<List<Dictionary<string, object>>> FetchSchoolsAsync(double latitude, double longitude);
        
        /// <summary>
        /// Fetches nearby hospitals
        /// </summary>
        Task<List<Dictionary<string, object>>> FetchHospitalsAsync(double latitude, double longitude);
        
        /// <summary>
        /// Calculates distance between two coordinates
        /// </summary>
        double CalculateDistance(double lat1, double lon1, double lat2, double lon2);
    }
}
