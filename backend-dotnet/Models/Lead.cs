namespace HyderabadUrbanReality.Models
{
    public class Lead
    {
        public string Name { get; set; } = string.Empty;
        public string Email { get; set; } = string.Empty;
        public string Mobile { get; set; } = string.Empty;
        public string AreaOfInterest { get; set; } = string.Empty;
        public string? ProjectName { get; set; }
        public string? ProjectId { get; set; }
        public string? DeviceFingerprint { get; set; }
        public DateTime Timestamp { get; set; } = DateTime.UtcNow;
        public string Source { get; set; } = "property_detail_page";
    }
}
