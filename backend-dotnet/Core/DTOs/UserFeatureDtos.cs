using System.Text.Json;

namespace HyderabadUrbanReality.Core.DTOs
{
    // Saved Property DTOs
    public record SavedPropertyDto(
        Guid Id,
        string ProjectId,
        string ProjectName,
        string? Locality,
        string? District,
        string? ProjectStatus,
        string? Notes,
        DateTime SavedAt);

    public record AddSavedPropertyRequestDto(string ProjectId, string? Notes);

    // Saved Search DTOs
    public record SavedSearchDto(
        Guid Id,
        string Name,
        JsonElement Filters,
        int? ResultCount,
        DateTime? LastRunAt,
        DateTime CreatedAt);

    public record AddSavedSearchRequestDto(string Name, JsonElement Filters);

    public record UpdateSavedSearchRequestDto(string? Name, JsonElement? Filters);

    // Comparison Result DTOs
    public record ComparisonResultDto(Guid Id, string? Name, string[] ProjectIds, DateTime CreatedAt);

    public record AddComparisonRequestDto(string? Name, string[] ProjectIds);
}
