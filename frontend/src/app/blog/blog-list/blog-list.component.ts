import { Component, OnInit } from '@angular/core';
import { Title, Meta } from '@angular/platform-browser';
import { BlogService, BlogArticle } from '../blog.service';

@Component({
  selector: 'app-blog-list',
  templateUrl: './blog-list.component.html',
  styleUrls: ['./blog-list.component.css']
})
export class BlogListComponent implements OnInit {
  articles: BlogArticle[] = [];
  filtered: BlogArticle[] = [];
  categories: { name: string; slug: string; count: number }[] = [];
  tags: string[] = [];

  activeCategory = 'all';
  searchQuery = '';

  constructor(private blog: BlogService, private titleSvc: Title, private meta: Meta) {}

  ngOnInit(): void {
    this.titleSvc.setTitle('Real Estate Blog — Hyderabad Property Insights | Hyderabad Urban Realty');
    this.meta.updateTag({ name: 'description', content: 'Expert articles on Hyderabad real estate — RERA compliance, property prices, NRI investment guide, stamp duty, locality analysis and market trends.' });
    this.meta.updateTag({ name: 'keywords', content: 'Hyderabad real estate blog, property market analysis, RERA Telangana, NRI property investment, home loan Hyderabad' });
    this.meta.updateTag({ property: 'og:title', content: 'Hyderabad Real Estate Blog — Market Insights & Buyer Guides' });
    this.meta.updateTag({ property: 'og:description', content: 'Data-backed property insights for Hyderabad buyers, investors and NRIs.' });

    this.articles  = this.blog.getAll();
    this.filtered  = this.articles;
    this.categories = this.blog.getAllCategories();
    this.tags      = this.blog.getAllTags();
  }

  filter(categorySlug: string): void {
    this.activeCategory = categorySlug;
    this.applyFilters();
  }

  onSearch(): void { this.applyFilters(); }

  private applyFilters(): void {
    let result = this.articles;
    if (this.activeCategory !== 'all') {
      result = result.filter(a => a.categorySlug === this.activeCategory);
    }
    if (this.searchQuery.trim()) {
      const q = this.searchQuery.toLowerCase();
      result = result.filter(a =>
        a.title.toLowerCase().includes(q) ||
        a.excerpt.toLowerCase().includes(q) ||
        a.tags.some(t => t.toLowerCase().includes(q))
      );
    }
    this.filtered = result;
  }

  get featuredArticle(): BlogArticle | undefined { return this.filtered[0]; }
  get restArticles(): BlogArticle[] { return this.filtered.slice(1); }

  formatDate(d: string): string {
    return new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' });
  }
}
