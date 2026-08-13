namespace HyderabadUrbanReality.Core.DTOs
{
    /// <summary>
    /// Request body for POST /api/geocode
    /// </summary>
    public class GeocodeRequest
    {
        public string? Street   { get; set; }
        public string? Landmark { get; set; }
        public string? Locality { get; set; }
        public string? District { get; set; }
        public string? PinCode  { get; set; }
    }
}
