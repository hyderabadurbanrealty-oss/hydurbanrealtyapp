namespace HyderabadUrbanReality.Core.DTOs
{
    public class ReraSettings
    {
        public string BaseUrl { get; set; } = "https://hrera.telangana.gov.in";
        public string SearchUrl { get; set; } = "";
        public int TimeoutSeconds { get; set; } = 30;
        public int MaxRetries { get; set; } = 3;
    }
}