namespace HyderabadUrbanReality.Core.Entities
{
    public class ComparisonResult
    {
        public Guid Id { get; set; }
        public Guid UserId { get; set; }
        public string? Name { get; set; }
        public string[] ProjectIds { get; set; } = Array.Empty<string>();
        public string? Snapshot { get; set; } // JSONB stored as string
        public DateTime CreatedAt { get; set; }
        public DateTime UpdatedAt { get; set; }
    }
}
