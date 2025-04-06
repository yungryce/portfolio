import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CliToolComponent } from './cli-tool.component';

describe('CliToolComponent', () => {
  let component: CliToolComponent;
  let fixture: ComponentFixture<CliToolComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CliToolComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(CliToolComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
