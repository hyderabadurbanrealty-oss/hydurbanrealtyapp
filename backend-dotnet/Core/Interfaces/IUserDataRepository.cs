using HyderabadUrbanReality.Core.Entities;
using System.Text.Json;

namespace HyderabadUrbanReality.Core.Interfaces
{
    /// <summary>
    /// Data access contract for user personalisation features:
    /// saved properties, favorites, saved searches, and comparison results.
    /// </summary>
    public interface IUserDataRepository
    {
        // ── Saved Properties ──────────────────────────────────────────────────
        Task<IEnumerable<SavedProperty>> GetSavedPropertiesAsync(Guid userId);
        Task<SavedProperty?> GetSavedPropertyAsync(Guid userId, string projectId);
        Task<SavedProperty> AddSavedPropertyAsync(SavedProperty item);
        Task RemoveSavedPropertyAsync(Guid userId, string projectId);

        // ── Favorites ─────────────────────────────────────────────────────────
        Task<IEnumerable<Favorite>> GetFavoritesAsync(Guid userId);
        Task<bool> IsFavoritedAsync(Guid userId, string projectId);
        Task AddFavoriteAsync(Guid userId, string projectId);
        Task RemoveFavoriteAsync(Guid userId, string projectId);

        // ── Saved Searches ────────────────────────────────────────────────────
        Task<IEnumerable<SavedSearch>> GetSavedSearchesAsync(Guid userId);
        Task<SavedSearch?> GetSavedSearchAsync(Guid userId, Guid searchId);
        Task<SavedSearch> AddSavedSearchAsync(SavedSearch search);
        Task<SavedSearch?> UpdateSavedSearchAsync(Guid userId, Guid searchId, string? name, JsonDocument? filters);
        Task DeleteSavedSearchAsync(Guid userId, Guid searchId);
        Task UpdateSavedSearchRunStatsAsync(Guid searchId, int resultCount);

        // ── Comparison Results ────────────────────────────────────────────────
        Task<IEnumerable<ComparisonResult>> GetComparisonsAsync(Guid userId);
        Task<ComparisonResult?> GetComparisonAsync(Guid userId, Guid comparisonId);
        Task<ComparisonResult> AddComparisonAsync(ComparisonResult comparison);
        Task DeleteComparisonAsync(Guid userId, Guid comparisonId);
    }
}
