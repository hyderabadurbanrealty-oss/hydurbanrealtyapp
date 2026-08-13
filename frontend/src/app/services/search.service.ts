import { Injectable } from '@angular/core';
import { Property } from '../map/map.component';

interface SearchIndex {
  [key: string]: Set<number>; // word -> property indices
}

@Injectable({
  providedIn: 'root'
})
export class SearchService {
  private searchIndex: SearchIndex = {};
  private properties: Property[] = [];
  private normalizedProperties: Map<number, string> = new Map(); // Cache normalized strings

  /**
   * Build an inverted index for fast searching
   * Time Complexity: O(n × m) one-time cost
   * Space Complexity: O(n × m)
   * 
   * This indexes all searchable fields into a map of words to property indices
   */
  buildSearchIndex(properties: Property[]) {
    this.properties = properties;
    this.searchIndex = {};
    this.normalizedProperties.clear();

    properties.forEach((property, index) => {
      // Create a searchable string combining all fields
      const searchableFields = [
        property['Project Name'] || '',
        property['Locality'] || '',
        property['District'] || '',
        property['Village/City/Town'] || '',
        property['Project Type'] || '',
        property['Project Status'] || ''
      ];

      const combinedText = searchableFields.join(' ').toLowerCase();
      this.normalizedProperties.set(index, combinedText);

      // Tokenize and index words
      const words = combinedText.split(/\s+/).filter(w => w.length > 0);
      
      words.forEach(word => {
        // Index full words
        if (!this.searchIndex[word]) {
          this.searchIndex[word] = new Set<number>();
        }
        this.searchIndex[word].add(index);

        // Index prefixes for autocomplete (optional, more memory)
        for (let i = 2; i <= word.length; i++) {
          const prefix = word.substring(0, i);
          if (!this.searchIndex[prefix]) {
            this.searchIndex[prefix] = new Set<number>();
          }
          this.searchIndex[prefix].add(index);
        }
      });
    });

  }

  /**
   * Fast search using inverted index
   * Time Complexity: O(k + r) where k = query terms, r = results
   * Much faster than O(n) linear search!
   */
  search(query: string, limit?: number): Property[] {
    if (!query || query.trim().length === 0) {
      return this.properties;
    }

    const normalizedQuery = query.toLowerCase().trim();
    const queryTerms = normalizedQuery.split(/\s+/).filter(t => t.length > 0);

    if (queryTerms.length === 0) {
      return this.properties;
    }

    // Find indices that match ALL query terms (AND operation)
    let matchingIndices: Set<number> | null = null;

    for (const term of queryTerms) {
      // Check if term exists in index
      const termMatches = this.searchIndex[term];
      
      if (!termMatches || termMatches.size === 0) {
        // If any term has no matches, do substring fallback
        return this.substringFallbackSearch(normalizedQuery, limit);
      }

      if (matchingIndices === null) {
        matchingIndices = new Set(termMatches);
      } else {
        // Intersect with previous matches
        matchingIndices = new Set(
          [...matchingIndices].filter(idx => termMatches.has(idx))
        );
      }

      // Early exit if no matches
      if (matchingIndices.size === 0) {
        return [];
      }
    }

    // Convert indices back to properties
    const results = matchingIndices 
      ? Array.from(matchingIndices).map(idx => this.properties[idx])
      : [];

    return limit ? results.slice(0, limit) : results;
  }

  /**
   * Fallback to substring search for partial word matches
   * Used when indexed search doesn't find exact word matches
   */
  private substringFallbackSearch(query: string, limit?: number): Property[] {
    const results: Property[] = [];
    
    for (let i = 0; i < this.properties.length; i++) {
      const normalizedText = this.normalizedProperties.get(i);
      if (normalizedText && normalizedText.includes(query)) {
        results.push(this.properties[i]);
        if (limit && results.length >= limit) {
          break;
        }
      }
    }
    
    return results;
  }

  /**
   * Get autocomplete suggestions
   * Optimized for fast prefix matching
   */
  getSuggestions(query: string, limit: number = 8): Property[] {
    return this.search(query, limit);
  }

  /**
   * Clear the search index (call when data changes)
   */
  clearIndex() {
    this.searchIndex = {};
    this.properties = [];
    this.normalizedProperties.clear();
  }
}
