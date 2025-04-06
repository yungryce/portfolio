import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ProjectAboutComponent } from './project-about.component';

describe('ProjectAboutComponent', () => {
  let component: ProjectAboutComponent;
  let fixture: ComponentFixture<ProjectAboutComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ProjectAboutComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(ProjectAboutComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
