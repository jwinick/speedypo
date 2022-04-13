library(jsonlite)
library(tidyverse)

setwd('/Users/jacobwinick/Dropbox/speedypo/speedy')
products <- fromJSON(txt ='products.txt',flatten = TRUE)
orders <- fromJSON(txt ='orders.txt',flatten = TRUE)

monthly_rev <- orders%>%
  as_tibble()%>%
  select(created_at,total_price)%>%
  mutate(date = as.Date(created),
         month = format(date,'%m-%Y'),
         price = as.numeric(total_price))%>%
  group_by(month)%>%
  summarize(revenue = sum(price,na.rm = T)/1000)%>%
  mutate(y = sub(".*-", "", month),
         m = sub("-.*", "", month),
         d = '01'
         )%>%
  unite('date',y:d,sep='-',remove=TRUE)%>%
  mutate(date = as.Date(date))%>%
  arrange(month)

rotate = element_text(angle=0)

plot <- ggplot(monthly_rev,aes(x=date,y=revenue))+
  geom_bar(stat='identity',fill='#0038B8')+
  xlab('Month')+
  ylab('Revenue (USD Thousand)')+
  ggtitle('Monthly Revenue')+
  scale_x_date(date_labels = '%b-%y')+
  theme_classic()


plot + theme(axis.title.y = element_text(angle=0,vjust =0.5),
             plot.title = element_text(hjust = 0.5))

