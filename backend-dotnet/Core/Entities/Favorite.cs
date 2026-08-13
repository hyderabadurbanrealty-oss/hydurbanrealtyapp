namespace HyderabadUrbanReality.Core.Entities
{
    public class Favorite
    {
        public Guid Id { get; set; }
        public Guid UserId { get; set; }
        public string ProjectId { get; set; } = string.Empty;
        public DateTime CreatedAt { get; set; }
    }
}
