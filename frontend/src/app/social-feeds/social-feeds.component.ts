import { Component, OnInit, OnDestroy } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { HttpClient } from '@angular/common/http';

interface TweetEmbed {
  url: string;
  html: string;
  authorName: string;
  authorUrl: string;
  safeHtml?: SafeHtml;
}

@Component({
  standalone: false,
  selector: 'app-social-feeds',
  templateUrl: './social-feeds.component.html',
  styleUrls: ['./social-feeds.component.css']
})
export class SocialFeedsComponent implements OnInit, OnDestroy {

  activeFeed: 'instagram' | 'twitter' = 'instagram';

  tweets: TweetEmbed[] = [];
  tweetsLoading = true;
  tweetsError = false;

  readonly handles = {
    instagram: 'hyderabadurbanrealty',
    twitter: 'HydUrbanRealty',
    whatsapp: 'https://whatsapp.com/channel/0029VadkpHVBKfhrgy5SKY1Q'
  };

  stats = [
    { label: 'Instagram', value: '@hyderabadurbanrealty', icon: 'instagram', color: '#E1306C', bg: '#fdf0f5' },
    { label: 'X / Twitter', value: '@hydurbanrealty', icon: 'twitter', color: '#000000', bg: '#f5f5f5' },
    { label: 'WhatsApp', value: 'Join Channel', icon: 'whatsapp', color: '#25d366', bg: '#f0fdf4' }
  ];

  scriptLoaded = false;
  private twitterScriptEl?: HTMLScriptElement;

  constructor(private sanitizer: DomSanitizer, private http: HttpClient) {}

  ngOnInit(): void {
    this.loadTweets();
  }

  ngOnDestroy(): void {
    if (this.twitterScriptEl) this.twitterScriptEl.remove();
  }

  switchFeed(feed: 'instagram' | 'twitter'): void {
    this.activeFeed = feed;
    if (feed !== 'instagram') setTimeout(() => this.loadWidgetsJs(), 200);
  }

  // Load tweets via backend proxy (oEmbed — no API key needed)
  loadTweets(): void {
    this.tweetsLoading = true;
    this.tweetsError = false;
    this.http.get<TweetEmbed[]>('/api/twitter/tweets').subscribe({
      next: (tweets) => {
        this.tweets = tweets.map(t => ({
          ...t,
          safeHtml: this.sanitizer.bypassSecurityTrustHtml(t.html)
        }));
        this.tweetsLoading = false;
        // Load widgets.js once so oEmbed HTML renders correctly
        setTimeout(() => this.loadWidgetsJs(), 200);
      },
      error: () => {
        this.tweetsError = true;
        this.tweetsLoading = false;
      }
    });
  }

  private loadWidgetsJs(): void {
    if ((window as any).twttr?.widgets) {
      (window as any).twttr.widgets.load();
      return;
    }
    if (document.querySelector('script[src*="widgets.js"]')) return;
    const s = document.createElement('script');
    s.src = 'https://platform.twitter.com/widgets.js';
    s.async = true;
    s.charset = 'utf-8';
    document.head.appendChild(s);
  }

  get showInstagram(): boolean {
    return this.activeFeed === 'instagram';
  }

  get showTwitter(): boolean {
    return this.activeFeed === 'twitter';
  }

  openWhatsApp(): void {
    window.open(this.handles.whatsapp, '_blank', 'noopener,noreferrer');
  }

  openInstagram(): void {
    window.open(`https://www.instagram.com/${this.handles.instagram}`, '_blank', 'noopener,noreferrer');
  }

  openTwitter(): void {
    window.open(`https://x.com/${this.handles.twitter}`, '_blank', 'noopener,noreferrer');
  }
}
