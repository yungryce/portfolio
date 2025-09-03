import { ApplicationConfig, provideZoneChangeDetection, importProvidersFrom, provideAppInitializer, inject } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { MarkdownModule } from 'ngx-markdown';
import { ConfigService } from './services/config.service';
import { firstValueFrom } from 'rxjs';

import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }), 
    provideRouter(routes),
    provideHttpClient(),
    importProvidersFrom(
      MarkdownModule.forRoot()
    ),
    provideAppInitializer(() => {
      const configService = inject(ConfigService);
      // const preFetchService = inject(PreFetchService);
      
      // // Load config first, then initialize prefetching
      // return firstValueFrom(configService.loadConfig()).then(() => {
      //   preFetchService.initialize();
      // });
    })
  ]
};
