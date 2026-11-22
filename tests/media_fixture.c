/* Independent input generator: all geometry is supplied by test facts. */
#include <cups/raster.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
int main(int argc, char **argv) {
  if (argc != 14) return 2;
  unsigned pw=atoi(argv[2]), ph=atoi(argv[3]), w=atoi(argv[4]), ht=atoi(argv[5]);
  unsigned xo=atoi(argv[6]), yo=atoi(argv[7]), strips=atoi(argv[8]);
  int full=atoi(argv[10]), pages=atoi(argv[11]), depth=atoi(argv[12]);
  cups_raster_t *r=cupsRasterOpen(STDOUT_FILENO,CUPS_RASTER_WRITE);
  if (!r) return 3;
  for (int page=0;page<pages;page++) {
    cups_page_header2_t h; memset(&h,0,sizeof h);
    h.HWResolution[0]=h.HWResolution[1]=300;
    h.PageSize[0]=(unsigned)(pw*.24+.5); h.PageSize[1]=(unsigned)(ph*.24+.5);
    h.cupsPageSize[0]=pw*.24; h.cupsPageSize[1]=ph*.24;
    h.cupsWidth=full?pw:w*strips; h.cupsHeight=full?ph:ht;
    h.cupsBitsPerColor=h.cupsBitsPerPixel=depth;
    h.cupsColorSpace=!strcmp(argv[13],"W")?CUPS_CSPACE_W:CUPS_CSPACE_K;
    h.cupsNumColors=1; h.NumCopies=1;
    h.cupsBytesPerLine=(h.cupsWidth*depth+7)/8;
    snprintf(h.cupsPageSizeName,sizeof h.cupsPageSizeName,"%s",argv[1]);
    if (!cupsRasterWriteHeader2(r,&h)) return 4;
    unsigned char *row=malloc(h.cupsBytesPerLine); if (!row) return 5;
    for (unsigned y=0;y<h.cupsHeight;y++) {
      memset(row,h.cupsColorSpace==CUPS_CSPACE_K?0:255,h.cupsBytesPerLine);
      for (unsigned x=0;x<h.cupsWidth;x++) {
        int ix=(int)x-(full?(int)xo:0), iy=(int)y-(full?(int)yo:0), black=0;
        if (!strcmp(argv[9],"edges")) black=iy==0 && ix>=0 && (ix%(int)w==0 || ix%(int)w==(int)w-1) && ix<(int)(w*strips);
        if (!strcmp(argv[9],"stripid")) black=iy==0 && ix>=0 && ix<(int)(w*strips) && ix%(int)w==page*(int)strips+ix/(int)w;
        if (!strcmp(argv[9],"cropmarks")) black=ix<0||ix>=(int)(w*strips)||iy<0||iy>=(int)ht;
        if (black) {
          if(depth==8) row[x]=h.cupsColorSpace==CUPS_CSPACE_K?255:0;
          else row[x/8]^=(unsigned char)(128>>(x%8));
        }
      }
      if(cupsRasterWritePixels(r,row,h.cupsBytesPerLine)!=h.cupsBytesPerLine) return 6;
    }
    free(row);
  }
  cupsRasterClose(r); return 0;
}
