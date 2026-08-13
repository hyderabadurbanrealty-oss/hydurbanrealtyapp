namespace HyderabadUrbanReality.Core.Entities
{
    public class SavedProperty
    {
        public Guid Id { get; set; }
        public Guid UserId { get; set; }
        public string ProjectId { get; set; } = string.Empty;
        public string? Notes { get; set; }
        public DateTime CreatedAt { get; set; }
    }
}
