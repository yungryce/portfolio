import { TestBed } from '@angular/core/testing';

import { GithubFilesService } from './github-files.service';

describe('GithubFilesService', () => {
  let service: GithubFilesService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(GithubFilesService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
