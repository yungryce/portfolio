import { ComponentFixture, TestBed } from '@angular/core/testing';

import { PortfolioAssistantComponent } from './portfolio-assistant.component';

describe('PortfolioAssistantComponent', () => {
  let component: PortfolioAssistantComponent;
  let fixture: ComponentFixture<PortfolioAssistantComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PortfolioAssistantComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(PortfolioAssistantComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
