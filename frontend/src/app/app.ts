import { Component, signal, inject } from '@angular/core';
import { Router, RouterLink, RouterOutlet } from '@angular/router';
import { AuthService } from './core/auth.service';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink],
  templateUrl: './app.html',
  styleUrl: './app.scss'
})
export class App {
  private auth = inject(AuthService);
  private router = inject(Router);
  protected readonly title = signal('frontend');
  get role() { return this.auth.role(); }
  get loggedIn() { return this.auth.isLoggedIn(); }
  logout() {
    this.auth.clear();
    this.router.navigateByUrl('/login');
  }
}
