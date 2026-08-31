import { Component, OnInit, OnDestroy } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { Title, Meta } from '@angular/platform-browser';
import { BlogService, BlogArticle } from '../blog.service';

@Component({
  standalone: false,
  selector: 'app-blog-detail',
  templateUrl: './blog-detail.component.html',
  styleUrls: ['./blog-detail.component.css']
})
export class BlogDetailComponent implements OnInit, OnDestroy {
  article?: BlogArticle;
  related: BlogArticle[] = [];
  notFound = false;
  readProgress = 0;

  private scrollListener?: () => void;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private blog: BlogService,
    private titleSvc: Title,
    private meta: Meta
  ) {}

  ngOnInit(): void {
    window.scrollTo(0, 0);
    const slug = this.route.snapshot.paramMap.get('slug') || '';
    const found = this.blog.getBySlug(slug);

    if (!found) { this.notFound = true; return; }

    this.article = found;
    this.related = this.blog.getRelated(found);

    // SEO tags
    this.titleSvc.setTitle(found.metaTitle);
    this.meta.updateTag({ name: 'description',  content: found.metaDescription });
    this.meta.updateTag({ name: 'keywords',     content: found.metaKeywords });
    this.meta.updateTag({ property: 'og:title', content: found.metaTitle });
    this.meta.updateTag({ property: 'og:description', content: found.metaDescription });
    this.meta.updateTag({ property: 'og:type',  content: 'article' });
    this.meta.updateTag({ name: 'twitter:card', content: 'summary_large_image' });
    this.meta.updateTag({ name: 'twitter:title', content: found.metaTitle });
    this.meta.updateTag({ name: 'twitter:description', content: found.metaDescription });

    // Reading progress
    this.scrollListener = () => {
      const el = document.documentElement;
      const scrolled = el.scrollTop || document.body.scrollTop;
      const total    = el.scrollHeight - el.clientHeight;
      this.readProgress = total > 0 ? Math.round((scrolled / total) * 100) : 0;
    };
    window.addEventListener('scroll', this.scrollListener);
  }

  ngOnDestroy(): void {
    if (this.scrollListener) window.removeEventListener('scroll', this.scrollListener);
  }

  formatDate(d: string): string {
    return new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' });
  }

  copyLink(): void {
    navigator.clipboard.writeText(window.location.href).catch(() => {});
  }
}
