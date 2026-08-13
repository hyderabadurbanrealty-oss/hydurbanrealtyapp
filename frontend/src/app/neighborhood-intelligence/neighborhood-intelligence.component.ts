import { Component, Input, OnInit } from '@angular/core';
import { PropertyService } from '../services/property.service';

@Component({
  selector: 'app-neighborhood-intelligence',
  templateUrl: './neighborhood-intelligence.component.html',
  styleUrls: ['./neighborhood-intelligence.component.css']
})
export class NeighborhoodIntelligenceComponent implements OnInit {
  @Input() property: any;
  
  neighborhoodScore: number = 0;
  amenities: any = {};
  nearbyPlaces: any[] = [];
  connectivityScore: number = 0;
  dataSource: string = 'loading'; // 'loading', 'OpenStreetMap', or 'unavailable'
  
  constructor(private propertyService: PropertyService) {}
  
  ngOnInit(): void {
    if (this.property) {
      this.loadNeighborhoodData();
    }
  }

  loadNeighborhoodData(): void {
    // Fetch cached neighborhood data (pre-populated during scraping)
    if (this.property.id || this.property.projectName) {
      const projectId = this.property.id || this.property.projectName;
      this.dataSource = 'loading';
      
      this.propertyService.getNeighborhoodData(projectId, false).subscribe({
        next: (data) => {
          if (data && Object.keys(data).length > 0 && this.hasRealData(data)) {
            // Real data exists (pre-fetched during scraping)
            this.amenities = this.transformApiData(data);
            this.dataSource = 'OpenStreetMap';
          } else {
            this.amenities = { schools: [], hospitals: [], transport: [], shopping: [], entertainment: [], parks: [] };
            this.dataSource = 'unavailable';
          }
        },
        error: () => {
          this.amenities = { schools: [], hospitals: [], transport: [], shopping: [], entertainment: [], parks: [] };
          this.dataSource = 'unavailable';
        }
      });
    } else {
      this.amenities = { schools: [], hospitals: [], transport: [], shopping: [], entertainment: [], parks: [] };
      this.dataSource = 'unavailable';
    }
  }

  hasRealData(data: any): boolean {
    // Check if the data has actual content (not empty arrays)
    return (data.schools && data.schools.length > 0) ||
           (data.hospitals && data.hospitals.length > 0) ||
           (data.transport && data.transport.length > 0);
  }

  transformApiData(data: any): any {
    // Transform API data to component format
    const transform = (items: any[], icon: string) => {
      return items.map((item: any) => ({
        ...item,
        distance: typeof item.distance === 'string' ? item.distance : `${item.distance} ${item.distanceUnit || 'km'}`,
        icon: icon,
        rating: item.rating || 0  // Ensure rating exists
      }));
    };

    const result = {
      schools: transform(data.schools || [], '🏫'),
      hospitals: transform(data.hospitals || [], '🏥'),
      transport: transform(data.transport || [], '🚇'),
      shopping: transform(data.shopping || [], '🛍️'),
      entertainment: transform(data.entertainment || [], '🎬'),
      parks: transform(data.parks || [], '🌳')
    };
    
    return result;
  }

  calculateNeighborhoodScore(): number {
    let score = 0;
    
    // Education (25 points)
    const schoolCount = this.amenities.schools?.length || 0;
    score += Math.min(schoolCount * 7, 25);
    
    // Healthcare (20 points)
    const hospitalCount = this.amenities.hospitals?.length || 0;
    score += Math.min(hospitalCount * 7, 20);
    
    // Transport (25 points)
    const transportCount = this.amenities.transport?.length || 0;
    score += Math.min(transportCount * 6, 25);
    
    // Shopping (15 points)
    const shoppingCount = this.amenities.shopping?.length || 0;
    score += Math.min(shoppingCount * 5, 15);
    
    // Entertainment & Parks (15 points)
    const entertainmentCount = (this.amenities.entertainment?.length || 0) + (this.amenities.parks?.length || 0);
    score += Math.min(entertainmentCount * 3, 15);
    
    this.neighborhoodScore = Math.min(Math.round(score), 100);
    return this.neighborhoodScore;
  }

  calculateConnectivityScore(): number {
    const transport = this.amenities.transport || [];
    let score = 0;
    
    // Check for different transport types
    if (transport.some((t: any) => t.type === 'Metro')) score += 30;
    if (transport.some((t: any) => t.type === 'Bus')) score += 25;
    if (transport.some((t: any) => t.type === 'Train')) score += 20;
    if (transport.some((t: any) => t.type === 'Airport')) score += 25;
    
    this.connectivityScore = Math.min(score, 100);
    return this.connectivityScore;
  }

  getScoreColor(score: number): string {
    if (score >= 80) return '#10b981';
    if (score >= 60) return '#3b82f6';
    if (score >= 40) return '#f59e0b';
    return '#ef4444';
  }

  getScoreLabel(score: number): string {
    if (score >= 80) return 'Excellent';
    if (score >= 60) return 'Good';
    if (score >= 40) return 'Average';
    return 'Fair';
  }

  getRatingStars(rating: number): string[] {
    const stars = [];
    const roundedRating = Math.round(rating || 0);
    for (let i = 1; i <= 5; i++) {
      stars.push(i <= roundedRating ? 'full' : 'empty');
    }
    return stars;
  }

  parseDistance(distance: string): number {
    const match = distance.match(/(\d+\.?\d*)/);
    return match ? parseFloat(match[1]) : 999;
  }

  getDistanceClass(distance: string): string {
    const dist = this.parseDistance(distance);
    if (dist <= 1) return 'very-close';
    if (dist <= 3) return 'close';
    if (dist <= 5) return 'moderate';
    return 'far';
  }

  getEntertainmentAndParks(): any[] {
    const entertainment = this.amenities.entertainment || [];
    const parks = this.amenities.parks || [];
    return [...entertainment, ...parks];
  }

  formatPlaceType(type: string): string {
    if (!type) return '';
    
    // Replace underscores with spaces and capitalize words
    return type
      .replace(/_/g, ' ')
      .split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(' ');
  }
}
