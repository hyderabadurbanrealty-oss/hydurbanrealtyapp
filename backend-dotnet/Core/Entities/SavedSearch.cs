namespace HyderabadUrbanReality.Core.Entities
{
    public class SavedSearch
    {
        public Guid Id { get; set; }
        public Guid UserId { get; set; }
        public string Name { get; set; } = string.Empty;
        public string Filters { get; set; } = "{}"; // JSONB stored as string
        public DateTime? LastRunAt { get; set; }
        public int? ResultCount { get; set; }
        public DateTime CreatedAt { get; set; }
        public DateTime UpdatedAt { get; set; }
    }
}
