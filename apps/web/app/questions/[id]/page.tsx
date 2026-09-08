import { ForecastRoom } from '../../../components/forecast-room';
export default async function QuestionPage({params}: {params: Promise<{id: string}>}) {
  const {id} = await params;
  return <ForecastRoom key={id} questionId={id} />;
}
