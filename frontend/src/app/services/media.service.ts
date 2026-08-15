import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface PropertyMedia {
  id: string;
  projectId: string;
  mediaType: 'image' | 'floorplan' | 'document' | 'video';
  title: string;
  fileUrl: string;
  fileName?: string;
  fileSize?: number;
  mimeType?: string;
  sortOrder: number;
  createdAt: string;
}

@Injectable({ providedIn: 'root' })
export class MediaService {
  constructor(private http: HttpClient) {}

  getMedia(projectId: string, type?: string): Observable<PropertyMedia[]> {
    const params = type ? new HttpParams().set('type', type) : undefined;
    return this.http.get<PropertyMedia[]>(
      `/api/projects/${encodeURIComponent(projectId)}/media`,
      { params }
    );
  }

  uploadFile(projectId: string, file: File, mediaType: string, title?: string, sortOrder = 0): Observable<any> {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('mediaType', mediaType);
    if (title) fd.append('title', title);
    fd.append('sortOrder', String(sortOrder));
    return this.http.post(`/api/projects/${encodeURIComponent(projectId)}/media/upload`, fd);
  }

  addVideo(projectId: string, url: string, title?: string): Observable<any> {
    return this.http.post(`/api/projects/${encodeURIComponent(projectId)}/media/video`, { url, title });
  }

  updateMedia(projectId: string, mediaId: string, title: string, sortOrder = 0): Observable<any> {
    return this.http.put(`/api/projects/${encodeURIComponent(projectId)}/media/${mediaId}`, { title, sortOrder });
  }

  deleteMedia(projectId: string, mediaId: string): Observable<any> {
    return this.http.delete(`/api/projects/${encodeURIComponent(projectId)}/media/${mediaId}`);
  }

  /** Register an already-scraped page URL directly in project_media without re-uploading the file */
  registerScrapedPage(projectId: string, fileUrl: string, title?: string, mediaType = 'floorplan', sortOrder = 0): Observable<any> {
    return this.http.post(`/api/projects/${encodeURIComponent(projectId)}/media/register-scraped`, {
      fileUrl,
      title: title || undefined,
      mediaType,
      sortOrder
    });
  }

  getYouTubeEmbedUrl(url: string): string {
    // Convert watch URLs and short URLs to embed format
    const match = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})/);
    return match ? `https://www.youtube.com/embed/${match[1]}` : url;
  }

  getYouTubeThumbnail(url: string): string {
    const match = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})/);
    return match ? `https://img.youtube.com/vi/${match[1]}/mqdefault.jpg` : '';
  }
}
