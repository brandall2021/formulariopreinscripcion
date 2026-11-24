import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { PanelComponent } from './panel.component';

describe('PanelComponent', () => {
  let fixture: ComponentFixture<PanelComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PanelComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    fixture = TestBed.createComponent(PanelComponent);
    fixture.detectChanges();
  });

  it('muestra el estado vacío hasta cargar solicitudes', () => {
    expect(fixture.nativeElement.textContent).toContain('Sin solicitudes');
  });
});
