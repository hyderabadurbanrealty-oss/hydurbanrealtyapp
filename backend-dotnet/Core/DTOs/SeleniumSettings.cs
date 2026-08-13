namespace HyderabadUrbanReality.Core.DTOs
{
    public class SeleniumSettings
    {
        public string DriverPath { get; set; } = "";
        public bool Headless { get; set; } = true;
        public int TimeoutSeconds { get; set; } = 30;
        public string ChromeDriverPath { get; set; } = "";
    }
}