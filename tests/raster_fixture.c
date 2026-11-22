/* Independent CUPS raster input fixture, not linked with production code. */
#include <cups/raster.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
  if (argc != 10 && argc != 11) { fprintf(stderr,"roll depth space pages pattern full override-field override-value rows\n"); return 2; }
  int roll=atoi(argv[1]), depth=atoi(argv[2]), pages=atoi(argv[4]), full=atoi(argv[6]);
  int width=roll==103?1200:1164, height=roll==103?1822:1660;
  int pw=roll==103?1224:1200, ph=roll==103?1941:1804;
  int xoff=full?(roll==103?12:18):0, yoff=full?(roll==103?59:72):0;
  cups_raster_t *r=cupsRasterOpen(STDOUT_FILENO,argc==11&&!strcmp(argv[10],"compressed")?CUPS_RASTER_WRITE_COMPRESSED:CUPS_RASTER_WRITE);
  if (!r) return 3;
  for(int page=0;page<pages;page++) {
    cups_page_header2_t h; memset(&h,0,sizeof h);
    h.HWResolution[0]=h.HWResolution[1]=300;
    h.PageSize[0]=(unsigned)(pw*72.0/300+0.5); h.PageSize[1]=(unsigned)(ph*72.0/300+0.5);
    h.cupsPageSize[0]=pw*72.0/300; h.cupsPageSize[1]=ph*72.0/300;
    h.cupsWidth=full?pw:width; h.cupsHeight=full?ph:height;
    h.cupsBitsPerColor=depth; h.cupsBitsPerPixel=depth;
    h.cupsColorSpace=!strcmp(argv[3],"K")?CUPS_CSPACE_K:CUPS_CSPACE_W;
    h.cupsColorOrder=CUPS_ORDER_CHUNKED; h.cupsNumColors=1;
    h.cupsBytesPerLine=(h.cupsWidth*depth+7)/8;
    h.NumCopies=1;
    snprintf(h.cupsPageSizeName,sizeof h.cupsPageSizeName,"w%dh%d",roll,roll==103?164:152);
    unsigned value=(unsigned)strtoul(argv[8],NULL,10);
    if(!strcmp(argv[7],"copies")) h.NumCopies=value;
    if(!strcmp(argv[7],"duplex")) h.Duplex=value;
    if(!strcmp(argv[7],"width")) h.cupsWidth=value;
    if(!strcmp(argv[7],"height")) h.cupsHeight=value;
    if(!strcmp(argv[7],"bpl")) h.cupsBytesPerLine=value;
    if(!strcmp(argv[7],"dpi")) h.HWResolution[0]=value;
    if(!strcmp(argv[7],"colors")) h.cupsNumColors=value;
    if(!strcmp(argv[7],"order")) h.cupsColorOrder=(cups_order_t)value;
    if(!strcmp(argv[7],"space")) h.cupsColorSpace=(cups_cspace_t)value;
    if(!strcmp(argv[7],"pagewidth")) h.cupsPageSize[0]=value;
    if(!cupsRasterWriteHeader2(r,&h)) return 4;
    /* Deliberately malformed headers need no payload. */
    if(strcmp(argv[7],"none")) break;
    unsigned char *row=malloc(h.cupsBytesPerLine); if(!row) return 5;
    unsigned rows=atoi(argv[9])<0?h.cupsHeight:(unsigned)atoi(argv[9]);
    for(unsigned y=0;y<rows;y++) {
      int isK=h.cupsColorSpace==CUPS_CSPACE_K;
      memset(row,isK?0:255,h.cupsBytesPerLine);
      for(unsigned x=0;x<h.cupsWidth;x++) {
        int ix=(int)x-xoff, iy=(int)y-yoff;
        int black=0;
        if(!strcmp(argv[5],"pageid")) black=iy==0&&ix==page;
        if(!strcmp(argv[5],"cropmarks")) black=ix<0||ix>=width||iy<0||iy>=height;
        if(!strcmp(argv[5],"black")) black=ix>=0&&ix<width&&iy>=0&&iy<height;
        if(!strcmp(argv[5],"edges")) black=(iy==0&&(ix==0||ix==width-1))||(iy==1&&ix==1)||(iy==height-1&&ix==7);
        if(!strcmp(argv[5],"asymmetric")) black=iy==0&&(ix==0||ix==2||ix==7||ix==8||ix==119);
        if(!strcmp(argv[5],"threshold")&&iy==0&&ix>=0&&ix<4&&depth==8) {
          static const unsigned char levels[]={0,127,128,255}; row[x]=levels[ix]; continue;
        }
        if(depth==8) row[x]=isK?(black?255:0):(black?0:255);
        else if(depth==1&&black) row[x/8]^=(unsigned char)(0x80>>(x%8));
      }
      if(cupsRasterWritePixels(r,row,h.cupsBytesPerLine)!=h.cupsBytesPerLine) return 6;
    }
    free(row);
  }
  cupsRasterClose(r); return 0;
}
